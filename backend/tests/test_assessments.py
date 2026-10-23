import io

from app.frameworks import load_framework, safeguards
from app.models import Role

CATALOGUE = safeguards()
IG1 = [sid for sid, s in CATALOGUE.items() if s["ig"] == 1]


def test_framework_matches_the_published_counts(client, make_user, auth):
    user, _ = make_user(Role.consultant)
    body = client.get("/api/assessments/framework", headers=auth(user)).json()
    all_safeguards = [s for c in body["controls"] for s in c["safeguards"]]
    assert len(body["controls"]) == 18
    assert len(all_safeguards) == 153
    assert len({s["id"] for s in all_safeguards}) == 153
    # Implementation groups are cumulative.
    assert sum(1 for s in all_safeguards if s["ig"] <= 1) == 56
    assert sum(1 for s in all_safeguards if s["ig"] <= 2) == 130
    assert sum(1 for s in all_safeguards if s["ig"] <= 3) == 153
    # The safeguard that a float-valued cell would otherwise collapse onto 3.1.
    assert CATALOGUE["3.10"]["title"] == "Encrypt Sensitive Data in Transit"


def _assessment(client, headers, org, target_ig=1):
    response = client.post(
        "/api/assessments",
        json={"client_id": str(org.id), "target_ig": target_ig, "name": "Базовая оценка"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_new_assessment_starts_empty_with_every_ig1_safeguard_open(
    client, make_user, make_client_org, auth
):
    org = make_client_org()
    consultant, _ = make_user(Role.consultant, clients=[org])
    body = _assessment(client, auth(consultant), org)

    assert body["status"] == "draft"
    assert body["result"]["overall"]["implementation"] == 0.0
    assert body["result"]["progress"]["in_scope"] == 56
    assert len(body["result"]["gaps"]) == 56
    # Lowest group first, so IG1 leads the remediation list.
    assert {gap["ig"] for gap in body["result"]["gaps"]} == {1}


def test_partial_counts_half_and_not_applicable_leaves_the_ratio_alone(
    client, make_user, make_client_org, auth
):
    org = make_client_org()
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)
    assessment = _assessment(client, headers, org)

    items = [
        {"safeguard_id": IG1[0], "status": "implemented"},
        {"safeguard_id": IG1[1], "status": "partial"},
        {"safeguard_id": IG1[2], "status": "not_applicable"},
    ]
    body = client.patch(
        f"/api/assessments/{assessment['id']}/items", json={"items": items}, headers=headers
    ).json()

    overall = body["result"]["overall"]
    # 1.0 + 0.5 over the 55 safeguards still counted; the N/A one left both sides.
    assert overall["counted"] == 55
    assert overall["not_applicable"] == 1
    assert overall["implementation"] == round(1.5 / 55, 4)
    assert overall["in_scope"] == 56
    assert body["status"] == "in_progress"
    # Neither the implemented nor the not-applicable safeguard is a gap; partial is.
    gap_ids = {gap["safeguard_id"] for gap in body["result"]["gaps"]}
    assert IG1[0] not in gap_ids and IG1[2] not in gap_ids and IG1[1] in gap_ids


def test_all_implemented_reaches_full_readiness_for_the_target_group(
    client, make_user, make_client_org, auth
):
    org = make_client_org()
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)
    assessment = _assessment(client, headers, org)

    body = client.patch(
        f"/api/assessments/{assessment['id']}/items",
        json={"items": [{"safeguard_id": sid, "status": "implemented"} for sid in IG1]},
        headers=headers,
    ).json()

    assert body["result"]["overall"]["implementation"] == 1.0
    assert body["result"]["gaps"] == []
    assert body["result"]["progress"]["complete"] is True
    groups = body["result"]["implementation_groups"]
    assert groups["IG1"]["implementation"] == 1.0
    # IG2 includes IG1, so a complete IG1 is partial progress towards IG2.
    assert 0 < groups["IG2"]["implementation"] < 1


def test_raising_the_target_group_widens_the_scope(client, make_user, make_client_org, auth):
    org = make_client_org()
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)
    assessment = _assessment(client, headers, org)

    body = client.patch(
        f"/api/assessments/{assessment['id']}", json={"target_ig": 2}, headers=headers
    ).json()
    assert body["target_ig"] == 2
    assert body["result"]["progress"]["in_scope"] == 130
    assert len(body["result"]["gaps"]) == 130


def test_unknown_safeguards_are_rejected(client, make_user, make_client_org, auth):
    org = make_client_org()
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)
    assessment = _assessment(client, headers, org)
    response = client.patch(
        f"/api/assessments/{assessment['id']}/items",
        json={"items": [{"safeguard_id": "99.9", "status": "implemented"}]},
        headers=headers,
    )
    assert response.status_code == 400


def test_completed_assessment_is_closed_for_edits(client, make_user, make_client_org, auth):
    org = make_client_org()
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)
    assessment = _assessment(client, headers, org)

    done = client.patch(
        f"/api/assessments/{assessment['id']}", json={"status": "completed"}, headers=headers
    ).json()
    assert done["completed_at"] is not None
    blocked = client.patch(
        f"/api/assessments/{assessment['id']}/items",
        json={"items": [{"safeguard_id": IG1[0], "status": "implemented"}]},
        headers=headers,
    )
    assert blocked.status_code == 409


def test_assessments_are_scoped_to_the_callers_clients(
    client, make_user, make_client_org, auth
):
    mine, theirs = make_client_org("Мой"), make_client_org("Чужой")
    consultant, _ = make_user(Role.consultant, clients=[mine])
    admin, _ = make_user(Role.admin)
    _assessment(client, auth(consultant), mine)
    other = _assessment(client, auth(admin), theirs)

    listed = client.get("/api/assessments", headers=auth(consultant)).json()
    assert [row["client_name"] for row in listed] == ["Мой"]
    assert client.get(f"/api/assessments/{other['id']}", headers=auth(consultant)).status_code == 403
    assert len(client.get("/api/assessments", headers=auth(admin)).json()) == 2


def test_respondents_cannot_create_an_assessment(client, make_user, make_client_org, auth):
    org = make_client_org()
    respondent, _ = make_user(Role.respondent, clients=[org])
    response = client.post(
        "/api/assessments", json={"client_id": str(org.id)}, headers=auth(respondent)
    )
    assert response.status_code == 403


def test_remediation_export_lists_the_open_gaps(client, make_user, make_client_org, auth):
    org = make_client_org()
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)
    assessment = _assessment(client, headers, org)
    client.patch(
        f"/api/assessments/{assessment['id']}/items",
        json={
            "items": [
                {"safeguard_id": sid, "status": "implemented"}
                for sid in IG1
                if sid != "1.1"
            ]
            + [
                {
                    "safeguard_id": "1.1",
                    "status": "partial",
                    "owner": "А. Петров",
                    "due_date": "2026-12-01",
                    "priority": "high",
                    "notes": "Инвентаризация ведётся вручную",
                }
            ]
        },
        headers=headers,
    )

    export = client.get(f"/api/assessments/{assessment['id']}/remediation.csv", headers=headers)
    assert export.status_code == 200
    text = export.content.decode("utf-8-sig")
    lines = text.strip().split("\n")
    assert len(lines) == 2
    assert "1.1" in lines[1] and "А. Петров" in lines[1] and "2026-12-01" in lines[1]
    assert "высокий" in lines[1]


def test_evidence_round_trip(client, make_user, make_client_org, auth, tmp_path, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("EVIDENCE_DIR", str(tmp_path / "evidence"))

    org = make_client_org()
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)
    assessment = _assessment(client, headers, org)

    upload = client.post(
        f"/api/assessments/{assessment['id']}/items/1.1/evidence",
        files={"file": ("инвентарь.csv", io.BytesIO("актив;владелец\n".encode()), "text/csv")},
        headers=headers,
    )
    assert upload.status_code == 201, upload.text
    record = upload.json()
    assert record["filename"] == "инвентарь.csv"
    assert record["size_bytes"] > 0

    # The file shows up on the safeguard it backs up.
    detail = client.get(f"/api/assessments/{assessment['id']}", headers=headers).json()
    item = next(i for i in detail["items"] if i["safeguard_id"] == "1.1")
    assert [e["id"] for e in item["evidence"]] == [record["id"]]

    download = client.get(f"/api/evidence/{record['id']}", headers=headers)
    assert download.status_code == 200
    assert "актив" in download.content.decode()

    assert client.delete(f"/api/evidence/{record['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/evidence/{record['id']}", headers=headers).status_code == 404
    get_settings.cache_clear()


def test_evidence_rejects_an_unsupported_type(
    client, make_user, make_client_org, auth, tmp_path, monkeypatch
):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("EVIDENCE_DIR", str(tmp_path / "evidence"))
    org = make_client_org()
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)
    assessment = _assessment(client, headers, org)

    response = client.post(
        f"/api/assessments/{assessment['id']}/items/1.1/evidence",
        files={"file": ("payload.exe", io.BytesIO(b"MZ"), "application/x-msdownload")},
        headers=headers,
    )
    assert response.status_code == 415
    get_settings.cache_clear()


def test_evidence_is_not_readable_across_clients(
    client, make_user, make_client_org, auth, tmp_path, monkeypatch
):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("EVIDENCE_DIR", str(tmp_path / "evidence"))
    mine, theirs = make_client_org("Мой"), make_client_org("Чужой")
    admin, _ = make_user(Role.admin)
    outsider, _ = make_user(Role.consultant, clients=[mine])
    assessment = _assessment(client, auth(admin), theirs)
    record = client.post(
        f"/api/assessments/{assessment['id']}/items/1.1/evidence",
        files={"file": ("политика.txt", io.BytesIO(b"secret"), "text/plain")},
        headers=auth(admin),
    ).json()

    assert client.get(f"/api/evidence/{record['id']}", headers=auth(outsider)).status_code == 403
    get_settings.cache_clear()


def test_framework_version_is_recorded_on_the_assessment(
    client, make_user, make_client_org, auth
):
    org = make_client_org()
    consultant, _ = make_user(Role.consultant, clients=[org])
    body = _assessment(client, auth(consultant), org)
    assert body["framework"] == "cis"
    assert body["framework_version"] == load_framework()["version"]

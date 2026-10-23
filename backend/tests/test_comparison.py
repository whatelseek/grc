from app.models import Role


def _assessment(client, headers, org, name, items=()):
    body = client.post(
        "/api/assessments",
        json={"client_id": str(org.id), "target_ig": 1, "name": name},
        headers=headers,
    ).json()
    if items:
        client.patch(
            f"/api/assessments/{body['id']}/items", json={"items": list(items)}, headers=headers
        )
    return body


def test_comparison_reports_progress_and_regressions(client, make_user, make_client_org, auth):
    org = make_client_org()
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)

    spring = _assessment(
        client,
        headers,
        org,
        "Весна",
        [
            {"safeguard_id": "1.1", "status": "implemented"},
            {"safeguard_id": "1.2", "status": "not_implemented"},
            {"safeguard_id": "2.1", "status": "partial"},
            {"safeguard_id": "2.2", "status": "implemented"},
        ],
    )
    autumn = _assessment(
        client,
        headers,
        org,
        "Осень",
        [
            {"safeguard_id": "1.1", "status": "implemented"},  # unchanged
            {"safeguard_id": "1.2", "status": "implemented"},  # closed
            {"safeguard_id": "2.1", "status": "implemented"},  # improved
            {"safeguard_id": "2.2", "status": "partial"},  # regressed
        ],
    )

    body = client.get(
        f"/api/assessments/compare?base={spring['id']}&target={autumn['id']}", headers=headers
    ).json()

    assert body["base"]["name"] == "Весна"
    assert body["target"]["name"] == "Осень"
    assert body["overall_delta"] > 0

    improved = {row["safeguard_id"] for row in body["improved"]}
    regressed = {row["safeguard_id"] for row in body["regressed"]}
    assert improved == {"1.2", "2.1"}
    assert regressed == {"2.2"}
    assert {row["safeguard_id"] for row in body["gaps_closed"]} == {"1.2", "2.1"}
    assert {row["safeguard_id"] for row in body["gaps_opened"]} == {"2.2"}
    # Everything untouched in both audits counts as unchanged.
    assert body["unchanged"] == 153 - 3
    assert body["only_in_base"] == [] and body["only_in_target"] == []


def test_not_applicable_is_a_scope_change_not_progress(client, make_user, make_client_org, auth):
    org = make_client_org()
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)
    before = _assessment(
        client, headers, org, "До", [{"safeguard_id": "1.3", "status": "not_implemented"}]
    )
    after = _assessment(
        client, headers, org, "После", [{"safeguard_id": "1.3", "status": "not_applicable"}]
    )

    body = client.get(
        f"/api/assessments/compare?base={before['id']}&target={after['id']}", headers=headers
    ).json()
    assert body["improved"] == [] and body["regressed"] == []


def test_comparison_spans_catalogue_versions(client, make_user, make_client_org, auth):
    """A requirement that exists in only one version is listed, not counted as change."""
    org = make_client_org()
    admin, _ = make_user(Role.admin)
    headers = auth(admin)
    first = _assessment(client, headers, org, "По старой версии", [{"safeguard_id": "1.2", "status": "implemented"}])

    frameworks = client.get("/api/frameworks", headers=headers).json()
    published = next(f for f in frameworks if f["status"] == "published")
    draft = client.post(
        f"/api/frameworks/{published['id']}/draft", json={"version": "v9"}, headers=headers
    ).json()
    body = client.get(f"/api/frameworks/{draft['id']}", headers=headers).json()
    removed = next(s for s in body["controls"][0]["safeguards"] if s["id"] == "1.2")
    client.delete(f"/api/frameworks/safeguards/{removed['uuid']}", headers=headers)
    client.post(
        f"/api/frameworks/{draft['id']}/safeguards",
        json={"control_id": body["controls"][0]["id"], "code": "1.97", "title": "Новое", "ig": 1},
        headers=headers,
    )
    client.post(f"/api/frameworks/{draft['id']}/publish", headers=headers)

    second = _assessment(client, headers, org, "По новой версии")
    result = client.get(
        f"/api/assessments/compare?base={first['id']}&target={second['id']}", headers=headers
    ).json()

    assert result["only_in_base"] == ["1.2"]
    assert result["only_in_target"] == ["1.97"]
    assert all(row["safeguard_id"] != "1.2" for row in result["regressed"])


def test_comparison_refuses_mismatched_or_identical_inputs(
    client, make_user, make_client_org, auth
):
    one, two = make_client_org("Первый"), make_client_org("Второй")
    admin, _ = make_user(Role.admin)
    headers = auth(admin)
    a = _assessment(client, headers, one, "A")
    b = _assessment(client, headers, two, "B")

    assert (
        client.get(f"/api/assessments/compare?base={a['id']}&target={b['id']}", headers=headers).status_code
        == 400
    )
    assert (
        client.get(f"/api/assessments/compare?base={a['id']}&target={a['id']}", headers=headers).status_code
        == 400
    )


def test_comparison_is_scoped_to_the_callers_clients(client, make_user, make_client_org, auth):
    org = make_client_org()
    outsider_org = make_client_org("Чужой")
    admin, _ = make_user(Role.admin)
    outsider, _ = make_user(Role.consultant, clients=[outsider_org])
    first = _assessment(client, auth(admin), org, "A")
    second = _assessment(client, auth(admin), org, "B")

    assert (
        client.get(
            f"/api/assessments/compare?base={first['id']}&target={second['id']}",
            headers=auth(outsider),
        ).status_code
        == 403
    )

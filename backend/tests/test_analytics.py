from app.analytics import band_for
from app.models import Role
from app.scales import RPO_SCALE_HOURS, RTO_SCALE_HOURS, to_hours
from app.template import matrix_rows

GRID = matrix_rows()


def codes_for(part: int, damage_type: str) -> list[int]:
    return [
        code
        for code, meta in sorted(GRID.items())
        if meta["part"] == part and meta["damage_type"] == damage_type
    ]


def test_band_edges_follow_the_damage_ladder():
    assert band_for(None) is None
    assert band_for(0.25) == "Низкий"
    assert band_for(0.26) == "Средний"
    assert band_for(0.5) == "Средний"
    assert band_for(0.51) == "Высокий"
    assert band_for(0.75) == "Высокий"
    assert band_for(1.0) == "Крайне высокий"


def test_scale_labels_convert_to_hours():
    assert to_hours("24 часа", RTO_SCALE_HOURS) == (24, False)
    assert to_hours("0 (потеря недопустима)", RPO_SCALE_HOURS) == (0, False)
    # "longer than the scale" is not a number, and is reported as such.
    assert to_hours("более 7 суток", RTO_SCALE_HOURS) == (None, True)
    assert to_hours(None, RTO_SCALE_HOURS) == (None, False)
    assert to_hours("непонятно", RTO_SCALE_HOURS) == (None, False)


def _fill(client, headers, survey_id, availability_level, current_rto, current_rpo):
    answers = [
        {"question_code": code, "level": availability_level} for code in codes_for(3, "financial")
    ]
    answers += [{"question_code": 79, "text": current_rto}, {"question_code": 80, "text": current_rpo}]
    response = client.patch(
        f"/api/surveys/{survey_id}/answers", json={"answers": answers}, headers=headers
    )
    assert response.status_code == 200
    return response.json()


def test_portfolio_counts_bands_statuses_and_gaps(
    client, make_user, make_client_org, make_system, auth
):
    org = make_client_org("Ромашка")
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)

    # «Крайне высокий» from 30 minutes on: required RTO is 10 minutes, current is 24 h.
    critical = client.post(
        "/api/surveys", json={"system_id": str(make_system(org, "ERP").id)}, headers=headers
    ).json()
    _fill(client, headers, critical["id"], "Крайне высокий", "24 часа", "24 часа")

    # A mild system whose current capability already meets the objective.
    mild = client.post(
        "/api/surveys", json={"system_id": str(make_system(org, "Портал").id)}, headers=headers
    ).json()
    _fill(client, headers, mild["id"], "Низкий", "15 минут", "15 минут")

    body = client.get("/api/analytics", headers=headers).json()

    assert body["kpis"]["surveys_total"] == 2
    assert body["kpis"]["surveys_scored"] == 2
    assert body["kpis"]["surveys_complete"] == 0
    assert body["kpis"]["rto_gaps"] == 1

    profile = {row["band"]: row["count"] for row in body["criticality_profile"]}
    assert profile["Крайне высокий"] == 1
    assert profile["Низкий"] == 1
    assert [row["status"] for row in body["collection"]] == ["draft", "submitted", "reviewed"]
    assert body["collection"][0]["count"] == 2

    # Only systems with a calculated objective can be compared, worst gap first.
    # The all-«Низкий» system never reaches a threshold, so it sets no RTO at all.
    assert [row["system_name"] for row in body["recovery"]] == ["ERP"]
    erp = body["recovery"][0]
    assert erp["required_rto"] == round(0.5 / 3, 4)
    assert erp["current_rto"] == 24
    assert erp["rto_gap"] == round(24 - 0.5 / 3, 4)

    # The damage profile averages over the systems that answered that block:
    # ERP at 1.0 and Портал at 0.25.
    financial = next(d for d in body["damage_profile"] if d["damage_type"] == "financial")
    assert financial["availability"] == 0.625
    assert financial["systems"] == 2


def test_portfolio_is_scoped_to_the_callers_clients(
    client, make_user, make_client_org, make_system, auth
):
    mine, theirs = make_client_org("Мой"), make_client_org("Чужой")
    consultant, _ = make_user(Role.consultant, clients=[mine])
    admin, _ = make_user(Role.admin)
    client.post(
        "/api/surveys", json={"system_id": str(make_system(mine).id)}, headers=auth(consultant)
    )
    client.post("/api/surveys", json={"system_id": str(make_system(theirs).id)}, headers=auth(admin))

    assert client.get("/api/analytics", headers=auth(consultant)).json()["kpis"]["surveys_total"] == 1
    assert client.get("/api/analytics", headers=auth(admin)).json()["kpis"]["surveys_total"] == 2
    assert (
        client.get(f"/api/analytics?client_id={theirs.id}", headers=auth(consultant)).status_code
        == 403
    )


def test_empty_portfolio_returns_zeroed_structure(client, make_user, auth):
    user, _ = make_user(Role.admin)
    body = client.get("/api/analytics", headers=auth(user)).json()
    assert body["kpis"]["surveys_total"] == 0
    assert [row["count"] for row in body["criticality_profile"]] == [0, 0, 0, 0]
    assert body["recovery"] == []
    assert body["damage_profile"] == []


def test_recovery_controls_report_the_latest_assessment(
    client, make_user, make_client_org, make_system, auth
):
    """The analytics page links an RTO gap to the controls that would close it."""
    org = make_client_org("Ромашка")
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)
    client.post("/api/surveys", json={"system_id": str(make_system(org).id)}, headers=headers)

    assert client.get("/api/analytics", headers=headers).json()["recovery_controls"] == []

    assessment = client.post(
        "/api/assessments", json={"client_id": str(org.id), "target_ig": 1}, headers=headers
    ).json()
    client.patch(
        f"/api/assessments/{assessment['id']}/items",
        json={"items": [{"safeguard_id": "11.1", "status": "implemented"}]},
        headers=headers,
    )

    rows = client.get("/api/analytics", headers=headers).json()["recovery_controls"]
    assert len(rows) == 1
    assert rows[0]["client_name"] == "Ромашка"
    controls = {row["control"]: row for row in rows[0]["controls"]}
    assert set(controls) == {"11", "17"}
    # Control 11 has four IG1 safeguards; one implemented is a quarter of them.
    assert controls["11"]["implementation"] == 0.25
    assert controls["17"]["implementation"] == 0.0

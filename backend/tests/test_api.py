from app.models import Role
from app.template import matrix_rows, plain_questions, required_codes

GRID = matrix_rows()
PLAIN = plain_questions()


def fill_everything() -> list[dict]:
    """A complete, internally consistent set of answers."""
    answers = []
    for code in sorted(PLAIN):
        question = PLAIN[code]
        if question["kind"] == "multiselect3":
            answers.append({"question_code": code, "selections": ["Производство продукции"]})
        else:
            answers.append({"question_code": code, "text": f"ответ на {code}"})
    for code in sorted(GRID):
        answers.append({"question_code": code, "level": "Средний"})
    return answers


def test_login_rejects_bad_password(client, make_user):
    user, _ = make_user(Role.admin)
    response = client.post("/api/auth/login", json={"email": user.email, "password": "nope"})
    assert response.status_code == 401


def test_me_returns_role_and_clients(client, make_user, make_client_org, auth):
    org = make_client_org()
    user, _ = make_user(Role.consultant, clients=[org])
    body = client.get("/api/auth/me", headers=auth(user)).json()
    assert body["role"] == "consultant"
    assert body["client_ids"] == [str(org.id)]


def test_endpoints_require_a_token(client):
    assert client.get("/api/clients").status_code == 401
    assert client.get("/api/dashboard").status_code == 401


def test_client_list_is_scoped_to_assignments(client, make_user, make_client_org, auth):
    mine, theirs = make_client_org("Мой"), make_client_org("Чужой")
    consultant, _ = make_user(Role.consultant, clients=[mine])
    admin, _ = make_user(Role.admin)

    names = [c["name"] for c in client.get("/api/clients", headers=auth(consultant)).json()]
    assert names == ["Мой"]
    admin_names = {c["name"] for c in client.get("/api/clients", headers=auth(admin)).json()}
    assert admin_names == {"Мой", "Чужой"}
    assert client.get(f"/api/clients/{theirs.id}", headers=auth(consultant)).status_code == 403


def test_respondent_cannot_create_clients(client, make_user, auth):
    user, _ = make_user(Role.respondent)
    response = client.post("/api/clients", json={"name": "Новый"}, headers=auth(user))
    assert response.status_code == 403


def test_consultant_creating_a_client_keeps_access(client, make_user, auth):
    consultant, _ = make_user(Role.consultant)
    headers = auth(consultant)
    created = client.post("/api/clients", json={"name": "Свежий"}, headers=headers)
    assert created.status_code == 201
    assert [c["name"] for c in client.get("/api/clients", headers=headers).json()] == ["Свежий"]


def test_duplicate_system_name_per_client_is_rejected(
    client, make_user, make_client_org, auth
):
    org = make_client_org()
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)
    payload = {"name": "1С"}
    assert client.post(f"/api/clients/{org.id}/systems", json=payload, headers=headers).status_code == 201
    assert client.post(f"/api/clients/{org.id}/systems", json=payload, headers=headers).status_code == 409


def test_survey_lifecycle_scores_and_submits(
    client, make_user, make_client_org, make_system, auth
):
    org = make_client_org()
    system = make_system(org)
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)

    created = client.post("/api/surveys", json={"system_id": str(system.id)}, headers=headers)
    assert created.status_code == 201
    survey = created.json()
    assert survey["status"] == "draft"
    assert survey["result"]["progress"]["required_total"] == len(required_codes())
    assert survey["result"]["overall_criticality"] is None

    # Submitting an empty survey is refused.
    assert client.post(f"/api/surveys/{survey['id']}/submit", headers=headers).status_code == 400

    saved = client.patch(
        f"/api/surveys/{survey['id']}/answers",
        json={"answers": fill_everything()},
        headers=headers,
    )
    assert saved.status_code == 200
    result = saved.json()["result"]
    assert result["overall_criticality"] == 0.5
    assert result["progress"]["required_filled"] == result["progress"]["required_total"]
    assert result["progress"]["complete"] is True
    assert result["rto_hours"] == 0.5  # «Средний» already at 30 minutes

    submitted = client.post(f"/api/surveys/{survey['id']}/submit", headers=headers)
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"

    reviewed = client.post(f"/api/surveys/{survey['id']}/review", headers=headers)
    assert reviewed.json()["status"] == "reviewed"
    # A reviewed survey is closed for edits.
    assert (
        client.patch(
            f"/api/surveys/{survey['id']}/answers",
            json={"answers": [{"question_code": 1, "text": "x"}]},
            headers=headers,
        ).status_code
        == 409
    )


def test_answers_are_upserted_not_duplicated(
    client, make_user, make_client_org, make_system, auth
):
    org = make_client_org()
    system = make_system(org)
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)
    survey = client.post(
        "/api/surveys", json={"system_id": str(system.id)}, headers=headers
    ).json()

    for value in ("первый", "второй"):
        client.patch(
            f"/api/surveys/{survey['id']}/answers",
            json={"answers": [{"question_code": 1, "text": value}]},
            headers=headers,
        )
    detail = client.get(f"/api/surveys/{survey['id']}", headers=headers).json()
    assert [a for a in detail["answers"] if a["question_code"] == 1] == [
        {"question_code": 1, "text": "второй", "level": None, "selections": None}
    ]


def test_unknown_question_codes_and_levels_are_rejected(
    client, make_user, make_client_org, make_system, auth
):
    org = make_client_org()
    system = make_system(org)
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)
    survey = client.post(
        "/api/surveys", json={"system_id": str(system.id)}, headers=headers
    ).json()

    bad_code = client.patch(
        f"/api/surveys/{survey['id']}/answers",
        json={"answers": [{"question_code": 999, "text": "x"}]},
        headers=headers,
    )
    assert bad_code.status_code == 400
    bad_level = client.patch(
        f"/api/surveys/{survey['id']}/answers",
        json={"answers": [{"question_code": 20, "level": "Катастрофический"}]},
        headers=headers,
    )
    assert bad_level.status_code == 400


def test_respondent_sees_only_surveys_assigned_to_them(
    client, make_user, make_client_org, make_system, auth
):
    org = make_client_org()
    system = make_system(org)
    consultant, _ = make_user(Role.consultant, clients=[org])
    respondent, _ = make_user(Role.respondent, clients=[org])
    other, _ = make_user(Role.respondent, clients=[org])

    mine = client.post(
        "/api/surveys",
        json={"system_id": str(system.id), "assignee_id": str(respondent.id)},
        headers=auth(consultant),
    ).json()
    theirs = client.post(
        "/api/surveys",
        json={"system_id": str(system.id), "assignee_id": str(other.id)},
        headers=auth(consultant),
    ).json()

    headers = auth(respondent)
    listed = [s["id"] for s in client.get("/api/surveys", headers=headers).json()]
    assert listed == [mine["id"]]
    assert client.get(f"/api/surveys/{theirs['id']}", headers=headers).status_code == 403
    assert client.get(f"/api/surveys/{mine['id']}", headers=headers).status_code == 200


def test_dashboard_lists_scores_and_exports_csv(
    client, make_user, make_client_org, make_system, auth
):
    org = make_client_org("Ромашка")
    system = make_system(org, "1С: Бухгалтерия")
    other_org = make_client_org("Василёк")
    make_system(other_org, "WMS")
    consultant, _ = make_user(Role.consultant, clients=[org])
    headers = auth(consultant)

    survey = client.post(
        "/api/surveys", json={"system_id": str(system.id)}, headers=headers
    ).json()
    client.patch(
        f"/api/surveys/{survey['id']}/answers",
        json={"answers": fill_everything()},
        headers=headers,
    )

    rows = client.get("/api/dashboard", headers=headers).json()
    assert len(rows) == 1
    row = rows[0]
    assert row["client_name"] == "Ромашка"
    assert row["system_name"] == "1С: Бухгалтерия"
    assert row["overall_criticality"] == 0.5
    assert row["stated_mtpd"] == "ответ на 76"
    assert row["current_rpo"] == "ответ на 80"
    assert row["required_filled"] == row["required_total"]

    export = client.get("/api/dashboard/export.csv", headers=headers)
    assert export.status_code == 200
    text = export.content.decode("utf-8-sig")
    assert "Ромашка" in text and "1С: Бухгалтерия" in text
    assert "Василёк" not in text


def test_template_is_served_with_all_eighty_questions(client, make_user, auth):
    user, _ = make_user(Role.respondent)
    body = client.get("/api/template", headers=auth(user)).json()
    codes = {q["code"] for q in body["questions"]}
    codes |= {r["code"] for m in body["matrices"] for r in m["rows"]}
    assert codes == set(range(1, 81))
    assert len(body["option_lists"]["functional_area"]) == 10
    assert body["levels"] == ["Крайне высокий", "Высокий", "Средний", "Низкий"]


def test_only_admins_manage_users(client, make_user, make_client_org, auth):
    org = make_client_org()
    consultant, _ = make_user(Role.consultant, clients=[org])
    admin, _ = make_user(Role.admin)

    payload = {"email": "new@example.com", "password": "secret123", "role": "respondent"}
    assert client.post("/api/users", json=payload, headers=auth(consultant)).status_code == 403
    created = client.post(
        "/api/users", json={**payload, "client_ids": [str(org.id)]}, headers=auth(admin)
    )
    assert created.status_code == 201
    assert created.json()["client_ids"] == [str(org.id)]
    # Consultants may list users of their own clients to pick an assignee: the new
    # respondent and themselves, but not the admin, who is assigned to no client.
    emails = {u["email"] for u in client.get("/api/users", headers=auth(consultant)).json()}
    assert emails == {"new@example.com", consultant.email}

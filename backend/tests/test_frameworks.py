import uuid

from app.models import Role


def _published(client, headers):
    frameworks = client.get("/api/frameworks", headers=headers).json()
    return next(f for f in frameworks if f["status"] == "published")


def test_imported_catalogue_is_published_and_complete(client, make_user, auth):
    admin, _ = make_user(Role.admin)
    framework = _published(client, auth(admin))
    assert framework["key"] == "cis"
    assert framework["control_count"] == 18
    assert framework["safeguard_count"] == 153
    assert framework["custom_count"] == 0


def test_published_requirements_cannot_be_edited_in_place(client, make_user, auth):
    admin, _ = make_user(Role.admin)
    headers = auth(admin)
    framework = _published(client, headers)
    body = client.get(f"/api/frameworks/{framework['id']}", headers=headers).json()
    control = body["controls"][0]

    refused = client.patch(
        f"/api/frameworks/controls/{control['id']}", json={"title": "Переписано"}, headers=headers
    )
    assert refused.status_code == 409
    assert "черновик" in refused.json()["detail"]


def test_admin_edits_requirements_through_a_draft(client, make_user, auth):
    admin, _ = make_user(Role.admin)
    headers = auth(admin)
    published = _published(client, headers)

    draft = client.post(
        f"/api/frameworks/{published['id']}/draft",
        json={"version": "v8.1.2-mars", "notes": "Добавили внутренние требования"},
        headers=headers,
    ).json()
    assert draft["status"] == "draft"
    assert draft["safeguard_count"] == 153
    assert draft["derived_from_id"] == published["id"]

    body = client.get(f"/api/frameworks/{draft['id']}", headers=headers).json()
    control = body["controls"][0]

    # Edit an inherited requirement.
    first = control["safeguards"][0]
    edited = client.patch(
        f"/api/frameworks/safeguards/{first['uuid']}",
        json={"title": "Вести реестр активов в CMDB", "ig": 1},
        headers=headers,
    ).json()
    assert edited["controls"][0]["safeguards"][0]["title"] == "Вести реестр активов в CMDB"

    # Add a requirement of our own.
    added = client.post(
        f"/api/frameworks/{draft['id']}/safeguards",
        json={
            "control_id": control["id"],
            "code": "1.99",
            "title": "Сверять реестр активов с бухгалтерским учётом",
            "ig": 1,
            "asset_class": "Devices",
            "security_function": "Identify",
        },
        headers=headers,
    ).json()
    custom = next(s for s in added["controls"][0]["safeguards"] if s["id"] == "1.99")
    assert custom["is_custom"] is True
    assert added["safeguard_count"] == 154

    # And a whole control.
    with_control = client.post(
        f"/api/frameworks/{draft['id']}/controls",
        json={"number": "19", "title": "Внутренние требования компании"},
        headers=headers,
    ).json()
    assert len(with_control["controls"]) == 19

    published_draft = client.post(f"/api/frameworks/{draft['id']}/publish", headers=headers).json()
    assert published_draft["status"] == "published"
    assert published_draft["published_at"] is not None


def test_duplicate_codes_and_versions_are_rejected(client, make_user, auth):
    admin, _ = make_user(Role.admin)
    headers = auth(admin)
    published = _published(client, headers)
    draft = client.post(
        f"/api/frameworks/{published['id']}/draft", json={"version": "v9-draft"}, headers=headers
    ).json()

    again = client.post(
        f"/api/frameworks/{published['id']}/draft", json={"version": "v9-draft"}, headers=headers
    )
    assert again.status_code == 409

    body = client.get(f"/api/frameworks/{draft['id']}", headers=headers).json()
    control = body["controls"][0]
    clash = client.post(
        f"/api/frameworks/{draft['id']}/safeguards",
        json={"control_id": control["id"], "code": "1.1", "title": "Дубль"},
        headers=headers,
    )
    assert clash.status_code == 409


def test_only_admins_touch_the_catalogue(client, make_user, make_client_org, auth):
    org = make_client_org()
    consultant, _ = make_user(Role.consultant, clients=[org])
    admin, _ = make_user(Role.admin)
    published = _published(client, auth(admin))

    # Consultants read the catalogue but cannot change it.
    assert client.get("/api/frameworks", headers=auth(consultant)).status_code == 200
    assert (
        client.post(
            f"/api/frameworks/{published['id']}/draft",
            json={"version": "v-nope"},
            headers=auth(consultant),
        ).status_code
        == 403
    )


def test_a_published_version_in_use_cannot_be_deleted(client, make_user, make_client_org, auth):
    org = make_client_org()
    admin, _ = make_user(Role.admin)
    headers = auth(admin)
    published = _published(client, headers)
    client.post("/api/assessments", json={"client_id": str(org.id)}, headers=headers)

    refused = client.delete(f"/api/frameworks/{published['id']}", headers=headers)
    assert refused.status_code == 409


def test_editing_requirements_leaves_an_existing_assessment_untouched(
    client, make_user, make_client_org, auth
):
    """The point of versioning: a past audit keeps the requirements it was made against."""
    org = make_client_org()
    admin, _ = make_user(Role.admin)
    headers = auth(admin)
    published = _published(client, headers)

    assessment = client.post(
        "/api/assessments", json={"client_id": str(org.id), "target_ig": 1}, headers=headers
    ).json()
    before = assessment["result"]["progress"]["in_scope"]
    assert before == 56

    draft = client.post(
        f"/api/frameworks/{published['id']}/draft", json={"version": "v8.2"}, headers=headers
    ).json()
    body = client.get(f"/api/frameworks/{draft['id']}", headers=headers).json()
    client.post(
        f"/api/frameworks/{draft['id']}/safeguards",
        json={
            "control_id": body["controls"][0]["id"],
            "code": "1.98",
            "title": "Новое обязательное требование",
            "ig": 1,
        },
        headers=headers,
    )
    client.post(f"/api/frameworks/{draft['id']}/publish", headers=headers)

    unchanged = client.get(f"/api/assessments/{assessment['id']}", headers=headers).json()
    assert unchanged["framework_version"] == published["version"]
    assert unchanged["result"]["progress"]["in_scope"] == before

    # A new assessment picks up the newly published version.
    fresh = client.post(
        "/api/assessments", json={"client_id": str(org.id), "target_ig": 1}, headers=headers
    ).json()
    assert fresh["framework_version"] == "v8.2"
    assert fresh["result"]["progress"]["in_scope"] == before + 1


def test_migrating_an_assessment_keeps_verdicts_that_still_apply(
    client, make_user, make_client_org, auth
):
    org = make_client_org()
    admin, _ = make_user(Role.admin)
    headers = auth(admin)
    published = _published(client, headers)
    assessment = client.post(
        "/api/assessments", json={"client_id": str(org.id), "target_ig": 1}, headers=headers
    ).json()
    client.patch(
        f"/api/assessments/{assessment['id']}/items",
        json={
            "items": [
                {"safeguard_id": "1.1", "status": "implemented"},
                {"safeguard_id": "1.2", "status": "partial"},
            ]
        },
        headers=headers,
    )

    draft = client.post(
        f"/api/frameworks/{published['id']}/draft", json={"version": "v8.3"}, headers=headers
    ).json()
    body = client.get(f"/api/frameworks/{draft['id']}", headers=headers).json()
    dropped = next(s for s in body["controls"][0]["safeguards"] if s["id"] == "1.2")
    client.delete(f"/api/frameworks/safeguards/{dropped['uuid']}", headers=headers)
    client.post(f"/api/frameworks/{draft['id']}/publish", headers=headers)

    migrated = client.post(
        f"/api/assessments/{assessment['id']}/migrate",
        json={"framework_id": draft["id"]},
        headers=headers,
    ).json()
    assert migrated["framework_version"] == "v8.3"
    codes = {item["safeguard_id"]: item["status"] for item in migrated["items"]}
    assert codes == {"1.1": "implemented"}

    trail = client.get(f"/api/assessments/{assessment['id']}/history", headers=headers).json()
    fields = {entry["field"] for entry in trail}
    assert "framework_version" in fields and "migrated_out" in fields


def test_migrating_to_a_draft_is_refused(client, make_user, make_client_org, auth):
    org = make_client_org()
    admin, _ = make_user(Role.admin)
    headers = auth(admin)
    published = _published(client, headers)
    assessment = client.post(
        "/api/assessments", json={"client_id": str(org.id)}, headers=headers
    ).json()
    draft = client.post(
        f"/api/frameworks/{published['id']}/draft", json={"version": "v-draft"}, headers=headers
    ).json()

    refused = client.post(
        f"/api/assessments/{assessment['id']}/migrate",
        json={"framework_id": draft["id"]},
        headers=headers,
    )
    assert refused.status_code == 409
    assert (
        client.post(
            f"/api/assessments/{assessment['id']}/migrate",
            json={"framework_id": str(uuid.uuid4())},
            headers=headers,
        ).status_code
        == 404
    )

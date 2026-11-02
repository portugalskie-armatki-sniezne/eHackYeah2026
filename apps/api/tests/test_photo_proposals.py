from uuid import uuid4

from fastapi.testclient import TestClient

from conftest import JPEG, PNG, create_report, random_location


def offer(client: TestClient, master_id: str, headers: dict[str, str], image: bytes = JPEG):
    return client.post(
        f"/master-reports/{master_id}/photo-proposals",
        files={"photo": ("offered", image)},
        headers=headers,
    )


def test_offered_photo_waits_for_the_reporter(client: TestClient, signed_in):
    _, headers = signed_in("user")
    neighbour, other_headers = signed_in("user")
    master_id = create_report(client, headers, random_location())["master_report_id"]

    assert offer(client, master_id, {}).status_code == 401
    assert offer(client, master_id, other_headers, image=b"not-an-image").status_code == 422
    response = offer(client, master_id, other_headers)
    assert response.status_code == 201, response.text
    proposal = response.json()
    assert proposal["state"] == "pending" and proposal["user_id"] == neighbour["id"]
    assert proposal["decided_at"] is None
    assert proposal["url"] == f"/photo-proposals/{proposal['id']}/file"

    # one photo waits at a time, and the case still counts as having none.
    assert offer(client, master_id, other_headers).status_code == 409
    master = client.get(f"/master-reports/{master_id}").json()
    assert master["photo_url"] is None
    assert master["pending_photo_url"] == proposal["url"]
    assert client.get(f"/master-reports/{master_id}/photo-proposals").json()["items"] == [proposal]
    assert client.get(proposal["url"]).status_code == 200

    # only the resident who filed the case decides about it.
    assert client.post(f"/photo-proposals/{proposal['id']}/approve").status_code == 401
    assert client.post(f"/photo-proposals/{proposal['id']}/approve", headers=other_headers).status_code == 403

    approved = client.post(f"/photo-proposals/{proposal['id']}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "approved" and approved.json()["decided_at"] is not None
    # a decided photo cannot be decided on again.
    assert client.post(f"/photo-proposals/{proposal['id']}/reject", headers=headers).status_code == 409

    master = client.get(f"/master-reports/{master_id}").json()
    assert master["pending_photo_url"] is None
    assert len(master["photos"]) == 1
    assert client.get(master["photo_url"]).status_code == 200
    # the case has a photo now, so nobody is asked for another.
    assert offer(client, master_id, other_headers).status_code == 409

    notification = client.get("/notifications", headers=other_headers).json()["items"][0]
    assert notification["kind"] == "photo_approved"
    assert notification["photo_proposal_state"] == "approved"


def test_the_reporter_is_asked_and_can_turn_a_photo_down(client: TestClient, signed_in, upload_dir):
    _, headers = signed_in("user")
    _, other_headers = signed_in("user")
    master_id = create_report(client, headers, random_location())["master_report_id"]
    proposal = offer(client, master_id, other_headers, image=PNG).json()

    asked = client.get("/notifications", headers=headers).json()["items"][0]
    assert asked["kind"] == "photo_proposal"
    assert asked["photo_proposal_id"] == proposal["id"]
    assert asked["photo_proposal_state"] == "pending"
    assert asked["photo_proposal_url"] == proposal["url"]

    rejected = client.post(f"/photo-proposals/{proposal['id']}/reject", headers=headers)
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["state"] == "rejected"
    # the file goes with the decision, and the case stays open for another photo.
    assert not (upload_dir / proposal["storage_key"]).exists()
    assert client.get(proposal["url"]).status_code == 404
    assert client.get(f"/master-reports/{master_id}").json()["pending_photo_url"] is None
    assert offer(client, master_id, other_headers).status_code == 201

    told = client.get("/notifications", headers=other_headers).json()["items"][0]
    assert told["kind"] == "photo_rejected" and told["photo_proposal_state"] == "rejected"


def test_the_reporter_needs_no_approval_for_their_own_photo(client: TestClient, signed_in):
    _, headers = signed_in("user")
    master_id = create_report(client, headers, random_location())["master_report_id"]

    proposal = offer(client, master_id, headers).json()

    assert proposal["state"] == "approved"
    master = client.get(f"/master-reports/{master_id}").json()
    assert master["pending_photo_url"] is None and master["photo_url"] is not None
    # nobody is told about a decision they made themselves.
    assert client.get("/notifications", headers=headers).json()["total"] == 0


def test_missing_cases_and_proposals(client: TestClient, signed_in):
    _, headers = signed_in("user")

    assert offer(client, str(uuid4()), headers).status_code == 404
    assert client.get(f"/photo-proposals/{uuid4()}/file").status_code == 404
    assert client.post(f"/photo-proposals/{uuid4()}/approve", headers=headers).status_code == 404
    assert client.post(f"/photo-proposals/{uuid4()}/reject", headers=headers).status_code == 404

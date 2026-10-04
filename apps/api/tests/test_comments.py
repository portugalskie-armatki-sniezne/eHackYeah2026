from uuid import uuid4

from fastapi.testclient import TestClient

from conftest import create_report, random_location


def test_comments_and_likes(client: TestClient, signed_in):
    author, headers = signed_in("user")
    _, other_headers = signed_in("user")
    master_id = create_report(client, headers, random_location())["master_report_id"]
    url = f"/master-reports/{master_id}/comments"

    assert client.post(url, json={"content": "Potwierdzam"}).status_code == 401
    assert client.post(url, json={"content": "   "}, headers=headers).status_code == 422
    response = client.post(url, json={"content": "  Potwierdzam  "}, headers=headers)
    assert response.status_code == 201
    comment = response.json()
    assert comment | {"id": None, "created_at": None} == {
        "id": None,
        "master_report_id": master_id,
        "user_id": author["id"],
        "author_first_name": author["first_name"],
        "content": "Potwierdzam",
        "like_count": 0,
        "liked_by_me": False,
        "created_at": None,
    }
    like_url = f"/comments/{comment['id']}/like"

    for _ in range(2):
        liked = client.put(like_url, headers=other_headers).json()
        assert liked["like_count"] == 1 and liked["liked_by_me"] is True
    assert client.put(like_url).status_code == 401

    # comments are public, liked_by_me depends on the optional token.
    assert client.get(url).json()["items"][0]["liked_by_me"] is False
    assert client.get(url, headers=headers).json()["items"][0]["liked_by_me"] is False
    assert client.get(url, headers=other_headers).json()["items"][0] == liked
    assert client.get(url, headers={"Authorization": "Bearer invalid"}).status_code == 401

    unliked = client.delete(like_url, headers=other_headers).json()
    assert unliked["like_count"] == 0 and unliked["liked_by_me"] is False
    assert client.delete(like_url, headers=other_headers).status_code == 200


def test_comments_order_and_missing_resources(client: TestClient, signed_in):
    _, headers = signed_in("user")
    master_id = create_report(client, headers, random_location())["master_report_id"]
    url = f"/master-reports/{master_id}/comments"
    created = [client.post(url, json={"content": f"Komentarz {index}"}, headers=headers).json() for index in range(3)]

    page = client.get(url, params={"limit": 2}).json()

    assert page["total"] == 3 and page["limit"] == 2
    # created_at is the same within the test transaction, so the order falls back to id.
    assert [comment["id"] for comment in page["items"]] == sorted(comment["id"] for comment in created)[:2]
    missing = f"/master-reports/{uuid4()}/comments"
    assert client.get(missing).status_code == 404
    assert client.post(missing, json={"content": "X"}, headers=headers).status_code == 404
    assert client.put(f"/comments/{uuid4()}/like", headers=headers).status_code == 404
    assert client.delete(f"/comments/{uuid4()}/like", headers=headers).status_code == 404
    assert client.delete(f"/comments/{uuid4()}", headers=headers).status_code == 404


def test_comment_is_deleted_by_author_or_staff(client: TestClient, signed_in):
    _, headers = signed_in("user")
    _, other_headers = signed_in("user")
    _, office_headers = signed_in("office")
    _, admin_headers = signed_in("admin")
    master_id = create_report(client, headers, random_location())["master_report_id"]
    url = f"/master-reports/{master_id}/comments"
    comments = [client.post(url, json={"content": "Potwierdzam"}, headers=headers).json() for _ in range(3)]

    assert client.delete(f"/comments/{comments[0]['id']}", headers=other_headers).status_code == 403
    for comment, deleting_headers in zip(comments, (headers, office_headers, admin_headers), strict=True):
        assert client.delete(f"/comments/{comment['id']}", headers=deleting_headers).status_code == 204
    assert client.get(url).json()["total"] == 0


def test_deleting_last_report_deletes_master_discussion(client: TestClient, signed_in):
    _, headers = signed_in("user")
    report = create_report(client, headers, random_location())
    url = f"/master-reports/{report['master_report_id']}/comments"
    comment = client.post(url, json={"content": "Potwierdzam"}, headers=headers).json()

    assert client.delete(f"/reports/{report['id']}", headers=headers).status_code == 204

    assert client.get(url).status_code == 404
    assert client.put(f"/comments/{comment['id']}/like", headers=headers).status_code == 404

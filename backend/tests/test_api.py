def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_people_lists_everyone_manager_first(client):
    response = client.get("/api/people")
    assert response.status_code == 200

    people = response.json()
    assert len(people) == 8
    assert people[0] == {"id": 1, "name": "Maya Chen", "role": "manager"}
    assert all(p["role"] == "dev" for p in people[1:])

    dev_names = [p["name"] for p in people[1:]]
    assert dev_names == sorted(dev_names)

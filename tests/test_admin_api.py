from tests.conftest import make_xlsx_bytes


def _login_admin(client):
    resp = client.post("/login", data={"role": "admin", "password": "test-admin-pw"})
    assert resp.status_code in (200, 303)


def _ingest_sample(client):
    headers = ["Name", "Status", "City", "Amount", "Note"]
    rows = [
        ["Alise", "ok", "NYC", 10, "n1"],
        ["Bob", "unk", "LA", 20, "n2"],
    ]
    content = make_xlsx_bytes(headers, rows)
    resp = client.post(
        "/admin/ingest/xlsx",
        files={"file": ("data.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_exposed_columns_rejects_out_of_bounds_count(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    col_ids = [c["id"] for c in ingest["columns"]]

    resp_low = client.put("/admin/exposed-columns", json={"column_def_ids": col_ids[:2]})
    assert resp_low.status_code == 422

    resp_high = client.put("/admin/exposed-columns", json={"column_def_ids": col_ids + col_ids[:2]})
    assert resp_high.status_code == 422


def test_cell_rule_requires_exposed_column(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    col_ids = [c["id"] for c in ingest["columns"]]

    # Expose only the first 4 columns; the 5th (index 4) is left unexposed.
    resp = client.put("/admin/exposed-columns", json={"column_def_ids": col_ids[:4]})
    assert resp.status_code == 204

    unexposed_col = col_ids[4]
    resp2 = client.put(f"/admin/cell-rules/0/{unexposed_col}", json={"options": ["a", "b"]})
    assert resp2.status_code == 400


def test_cell_rule_requires_at_least_two_options(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    col_ids = [c["id"] for c in ingest["columns"]]
    client.put("/admin/exposed-columns", json={"column_def_ids": col_ids[:4]})

    resp = client.put(f"/admin/cell-rules/0/{col_ids[0]}", json={"options": ["only-one"]})
    assert resp.status_code == 422


def test_row_assignment_validates_enduser_and_persists(client):
    _login_admin(client)
    _ingest_sample(client)

    resp_bad = client.put("/admin/rows/0/assign", json={"enduser_id": 999})
    assert resp_bad.status_code == 400

    user_resp = client.post("/admin/endusers", json={"username": "alice", "password": "pw123"})
    assert user_resp.status_code == 201
    enduser_id = user_resp.json()["id"]

    resp_ok = client.put("/admin/rows/0/assign", json={"enduser_id": enduser_id})
    assert resp_ok.status_code == 204

    dataset = client.get("/admin/dataset").json()
    assert dataset["rows"][0]["assigned_enduser_id"] == enduser_id


def test_duplicate_enduser_username_rejected(client):
    _login_admin(client)
    client.post("/admin/endusers", json={"username": "alice", "password": "pw123"})
    resp = client.post("/admin/endusers", json={"username": "alice", "password": "other"})
    assert resp.status_code == 409


def test_bulk_row_assignment_shares_multiple_rows_at_once(client):
    _login_admin(client)
    _ingest_sample(client)
    user_resp = client.post("/admin/endusers", json={"username": "carol", "password": "pw123"})
    enduser_id = user_resp.json()["id"]

    resp = client.put("/admin/rows/assign-bulk", json={"row_indices": [0, 1], "enduser_id": enduser_id})
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2

    dataset = client.get("/admin/dataset").json()
    rows_by_index = {r["row_index"]: r for r in dataset["rows"]}
    assert rows_by_index[0]["assigned_enduser_id"] == enduser_id
    assert rows_by_index[1]["assigned_enduser_id"] == enduser_id


def test_bulk_row_assignment_rejects_unknown_row(client):
    _login_admin(client)
    _ingest_sample(client)

    resp = client.put("/admin/rows/assign-bulk", json={"row_indices": [0, 99], "enduser_id": None})
    assert resp.status_code == 404


def test_bulk_row_assignment_rejects_unknown_enduser(client):
    _login_admin(client)
    _ingest_sample(client)

    resp = client.put("/admin/rows/assign-bulk", json={"row_indices": [0], "enduser_id": 999})
    assert resp.status_code == 400


def test_bulk_row_assignment_can_unassign(client):
    _login_admin(client)
    _ingest_sample(client)
    user_resp = client.post("/admin/endusers", json={"username": "dave", "password": "pw123"})
    enduser_id = user_resp.json()["id"]
    client.put("/admin/rows/assign-bulk", json={"row_indices": [0], "enduser_id": enduser_id})

    resp = client.put("/admin/rows/assign-bulk", json={"row_indices": [0], "enduser_id": None})
    assert resp.status_code == 200

    dataset = client.get("/admin/dataset").json()
    row0 = next(r for r in dataset["rows"] if r["row_index"] == 0)
    assert row0["assigned_enduser_id"] is None

from tests.conftest import make_xlsx_bytes


def _login_admin(client):
    resp = client.post("/login", data={"role": "master_admin", "password": "test-admin-pw"})
    assert resp.status_code in (200, 303)


def _ingest_sample(client, label=None):
    headers = ["Name", "Status", "City", "Amount", "Note"]
    rows = [
        ["Alise", "ok", "NYC", 10, "n1"],
        ["Bob", "unk", "LA", 20, "n2"],
    ]
    content = make_xlsx_bytes(headers, rows)
    url = "/admin/ingest/xlsx" + (f"?label={label}" if label else "")
    resp = client.post(
        url,
        files={"file": ("data.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_ingest_creates_new_dataset_without_wiping_prior_ones(client):
    _login_admin(client)
    first = _ingest_sample(client, label="First")
    second = _ingest_sample(client, label="Second")

    assert first["dataset_id"] != second["dataset_id"]

    datasets = client.get("/admin/datasets").json()
    labels = {d["label"] for d in datasets}
    assert {"First", "Second"}.issubset(labels)

    # The first dataset's raw data is still readable — ingesting again didn't wipe it.
    resp = client.get(f"/admin/datasets/{first['dataset_id']}")
    assert resp.status_code == 200
    assert resp.json()["label"] == "First"


def test_exposed_columns_rejects_out_of_bounds_count(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]
    col_ids = [c["id"] for c in ingest["columns"]]

    resp_low = client.put(f"/admin/datasets/{ds_id}/exposed-columns", json={"column_def_ids": col_ids[:2]})
    assert resp_low.status_code == 422

    resp_high = client.put(
        f"/admin/datasets/{ds_id}/exposed-columns", json={"column_def_ids": col_ids + col_ids[:2]}
    )
    assert resp_high.status_code == 422


def test_cell_rule_requires_exposed_column(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]
    col_ids = [c["id"] for c in ingest["columns"]]

    # Expose only the first 4 columns; the 5th (index 4) is left unexposed.
    resp = client.put(f"/admin/datasets/{ds_id}/exposed-columns", json={"column_def_ids": col_ids[:4]})
    assert resp.status_code == 204

    unexposed_col = col_ids[4]
    resp2 = client.put(f"/admin/datasets/{ds_id}/cell-rules/0/{unexposed_col}", json={"options": ["a", "b"]})
    assert resp2.status_code == 400


def test_cell_rule_requires_at_least_two_options(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]
    col_ids = [c["id"] for c in ingest["columns"]]
    client.put(f"/admin/datasets/{ds_id}/exposed-columns", json={"column_def_ids": col_ids[:4]})

    resp = client.put(f"/admin/datasets/{ds_id}/cell-rules/0/{col_ids[0]}", json={"options": ["only-one"]})
    assert resp.status_code == 422


def test_row_assignment_validates_enduser_and_persists(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]

    resp_bad = client.put(f"/admin/datasets/{ds_id}/rows/0/assign", json={"enduser_id": 999})
    assert resp_bad.status_code == 400

    user_resp = client.post("/admin/endusers", json={"username": "alice", "password": "pw123"})
    assert user_resp.status_code == 201
    enduser_id = user_resp.json()["id"]

    resp_ok = client.put(f"/admin/datasets/{ds_id}/rows/0/assign", json={"enduser_id": enduser_id})
    assert resp_ok.status_code == 204

    dataset = client.get(f"/admin/datasets/{ds_id}").json()
    assert dataset["rows"][0]["assigned_enduser_id"] == enduser_id


def test_duplicate_enduser_username_rejected(client):
    _login_admin(client)
    client.post("/admin/endusers", json={"username": "alice", "password": "pw123"})
    resp = client.post("/admin/endusers", json={"username": "alice", "password": "other"})
    assert resp.status_code == 409


def test_bulk_row_assignment_shares_multiple_rows_at_once(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]
    user_resp = client.post("/admin/endusers", json={"username": "carol", "password": "pw123"})
    enduser_id = user_resp.json()["id"]

    resp = client.put(
        f"/admin/datasets/{ds_id}/rows/assign-bulk", json={"row_indices": [0, 1], "enduser_id": enduser_id}
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2

    dataset = client.get(f"/admin/datasets/{ds_id}").json()
    rows_by_index = {r["row_index"]: r for r in dataset["rows"]}
    assert rows_by_index[0]["assigned_enduser_id"] == enduser_id
    assert rows_by_index[1]["assigned_enduser_id"] == enduser_id


def test_bulk_row_assignment_rejects_unknown_row(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]

    resp = client.put(f"/admin/datasets/{ds_id}/rows/assign-bulk", json={"row_indices": [0, 99], "enduser_id": None})
    assert resp.status_code == 404


def test_bulk_row_assignment_rejects_unknown_enduser(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]

    resp = client.put(f"/admin/datasets/{ds_id}/rows/assign-bulk", json={"row_indices": [0], "enduser_id": 999})
    assert resp.status_code == 400


def test_bulk_row_assignment_can_unassign(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]
    user_resp = client.post("/admin/endusers", json={"username": "dave", "password": "pw123"})
    enduser_id = user_resp.json()["id"]
    client.put(f"/admin/datasets/{ds_id}/rows/assign-bulk", json={"row_indices": [0], "enduser_id": enduser_id})

    resp = client.put(f"/admin/datasets/{ds_id}/rows/assign-bulk", json={"row_indices": [0], "enduser_id": None})
    assert resp.status_code == 200

    dataset = client.get(f"/admin/datasets/{ds_id}").json()
    row0 = next(r for r in dataset["rows"] if r["row_index"] == 0)
    assert row0["assigned_enduser_id"] is None


def test_create_dropdown_admin_column(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]

    resp = client.post(
        f"/admin/datasets/{ds_id}/columns",
        json={"name": "Reviewer Notes", "input_type": "dropdown", "options": ["A", "B"]},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["is_admin_added"] is True
    assert body["input_type"] == "dropdown"
    assert body["options"] == ["A", "B"]
    assert body["safe_name"]

    dataset = client.get(f"/admin/datasets/{ds_id}").json()
    assert any(c["id"] == body["id"] for c in dataset["columns"])


def test_create_text_admin_column(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]

    resp = client.post(
        f"/admin/datasets/{ds_id}/columns", json={"name": "Free Notes", "input_type": "text", "options": None}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["input_type"] == "text"
    assert body["options"] is None


def test_dropdown_admin_column_requires_two_options(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]

    resp = client.post(
        f"/admin/datasets/{ds_id}/columns", json={"name": "Bad", "input_type": "dropdown", "options": ["only-one"]}
    )
    assert resp.status_code == 400


def test_admin_column_rejects_bad_input_type(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]

    resp = client.post(
        f"/admin/datasets/{ds_id}/columns", json={"name": "Bad", "input_type": "checkbox", "options": None}
    )
    assert resp.status_code == 400


def test_delete_admin_column(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]
    created = client.post(
        f"/admin/datasets/{ds_id}/columns", json={"name": "Temp", "input_type": "text", "options": None}
    ).json()

    resp = client.delete(f"/admin/datasets/{ds_id}/columns/{created['id']}")
    assert resp.status_code == 204

    dataset = client.get(f"/admin/datasets/{ds_id}").json()
    assert not any(c["id"] == created["id"] for c in dataset["columns"])


def test_cannot_delete_ingested_column(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]
    ingested_col_id = ingest["columns"][0]["id"]

    resp = client.delete(f"/admin/datasets/{ds_id}/columns/{ingested_col_id}")
    assert resp.status_code == 400


def test_create_admin_row_is_blank_and_assignable(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]

    resp = client.post(f"/admin/datasets/{ds_id}/rows")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["row_index"] == 2  # after the two ingested rows (0, 1)
    assert body["values"] == {}
    assert body["is_admin_added"] is True

    assign_resp = client.put(f"/admin/datasets/{ds_id}/rows/2/assign", json={"enduser_id": None})
    assert assign_resp.status_code == 204


def test_datasets_are_isolated_from_each_other(client):
    _login_admin(client)
    first = _ingest_sample(client, label="Isolated A")
    second = _ingest_sample(client, label="Isolated B")

    col_a = first["columns"][0]["id"]
    resp = client.put(f"/admin/datasets/{first['dataset_id']}/exposed-columns", json={"column_def_ids": [c["id"] for c in first["columns"][:4]]})
    assert resp.status_code == 204

    # A column id from dataset A must not be usable against dataset B.
    bad_resp = client.put(
        f"/admin/datasets/{second['dataset_id']}/exposed-columns", json={"column_def_ids": [col_a] + [c["id"] for c in second["columns"][:3]]}
    )
    assert bad_resp.status_code == 400


def test_metadata_reflects_input_and_output_columns(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]
    client.put(f"/admin/datasets/{ds_id}/target-table", json={"table_name": "meta_test_table"})

    resp = client.get(f"/admin/datasets/{ds_id}/metadata")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["target_table_name"] == "meta_test_table"
    assert body["row_count"] == 2
    assert {c["source_name"] for c in body["input_columns"]} == {"Name", "Status", "City", "Amount", "Note"}
    assert body["output_columns"] == body["input_columns"]


def test_ship_requires_target_table_and_publishes(client):
    _login_admin(client)
    ingest = _ingest_sample(client)
    ds_id = ingest["dataset_id"]

    not_configured = client.post(f"/admin/datasets/{ds_id}/ship")
    assert not_configured.status_code == 400

    client.put(f"/admin/datasets/{ds_id}/target-table", json={"table_name": "ship_test_table"})
    resp = client.post(f"/admin/datasets/{ds_id}/ship")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"table_name": "ship_test_table", "row_count": 2}


def test_db_connections_endpoint_lists_names_only(client, monkeypatch):
    monkeypatch.setenv("DB_CONN_TESTDB", "sqlite:///somewhere.db")
    _login_admin(client)

    resp = client.get("/admin/db-connections")
    assert resp.status_code == 200
    body = resp.json()
    assert "testdb" in body["names"]
    assert "sqlite:///somewhere.db" not in str(body)


def test_master_admin_can_create_list_and_remove_admin_accounts(client):
    _login_admin(client)

    create_resp = client.post("/admin/admins", json={"username": "ada", "password": "pw123"})
    assert create_resp.status_code == 201, create_resp.text
    admin_id = create_resp.json()["id"]

    list_resp = client.get("/admin/admins")
    assert list_resp.status_code == 200
    assert any(a["username"] == "ada" for a in list_resp.json())

    del_resp = client.delete(f"/admin/admins/{admin_id}")
    assert del_resp.status_code == 204

    list_resp2 = client.get("/admin/admins")
    assert not any(a["username"] == "ada" for a in list_resp2.json())


def test_duplicate_admin_username_rejected(client):
    _login_admin(client)
    client.post("/admin/admins", json={"username": "ada", "password": "pw123"})
    resp = client.post("/admin/admins", json={"username": "ada", "password": "other"})
    assert resp.status_code == 409


def test_delete_unknown_admin_returns_404(client):
    _login_admin(client)
    resp = client.delete("/admin/admins/999")
    assert resp.status_code == 404

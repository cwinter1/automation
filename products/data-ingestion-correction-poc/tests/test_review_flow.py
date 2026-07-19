from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from tests.conftest import make_xlsx_bytes


def _ingest_sample(admin_client, label=None):
    headers = ["Name", "Status", "City", "Amount", "Note"]
    rows = [
        ["Alise", "ok", "NYC", 10, "row0-alice-needs-name-fix"],
        ["Alice2", "ok", "SF", 11, "row1-alice-clean"],
        ["Carl", "unk", "LA", 12, "row2-bob-needs-status-fix"],
        ["Dana", "ok", "DC", 13, "row3-unassigned"],
    ]
    content = make_xlsx_bytes(headers, rows)
    url = "/admin/ingest/xlsx" + (f"?label={label}" if label else "")
    resp = admin_client.post(
        url,
        files={"file": ("data.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    col_ids = {c["source_name"]: c["id"] for c in body["columns"]}
    return body["dataset_id"], col_ids


def _setup_dataset(target_table="corrected_flow", label=None):
    admin_client = TestClient(app)
    admin_client.post("/login", data={"role": "master_admin", "password": "test-admin-pw"})

    ds_id, col_ids = _ingest_sample(admin_client, label=label)

    resp = admin_client.put(
        f"/admin/datasets/{ds_id}/exposed-columns",
        json={"column_def_ids": [col_ids["Name"], col_ids["Status"], col_ids["City"], col_ids["Amount"]]},
    )
    assert resp.status_code == 204

    resp = admin_client.put(f"/admin/datasets/{ds_id}/target-table", json={"table_name": target_table})
    assert resp.status_code == 204

    alice_resp = admin_client.post("/admin/endusers", json={"username": "alice", "password": "pw-alice"})
    bob_resp = admin_client.post("/admin/endusers", json={"username": "bob", "password": "pw-bob"})
    alice_id = alice_resp.json()["id"]
    bob_id = bob_resp.json()["id"]

    for row_index, enduser_id in [(0, alice_id), (1, alice_id), (2, bob_id)]:
        r = admin_client.put(f"/admin/datasets/{ds_id}/rows/{row_index}/assign", json={"enduser_id": enduser_id})
        assert r.status_code == 204
    # row_index 3 is left unassigned deliberately.

    r = admin_client.put(
        f"/admin/datasets/{ds_id}/cell-rules/0/{col_ids['Name']}", json={"options": ["Alice", "Alicia"]}
    )
    assert r.status_code == 204
    r = admin_client.put(
        f"/admin/datasets/{ds_id}/cell-rules/2/{col_ids['Status']}", json={"options": ["active", "inactive"]}
    )
    assert r.status_code == 204

    return ds_id, col_ids


def _target_table_rows(table_name="corrected_flow"):
    with engine.connect() as conn:
        return conn.execute(text(f'SELECT name, status, note FROM "{table_name}" ORDER BY id')).fetchall()


def test_full_review_save_ship_flow():
    ds_id, col_ids = _setup_dataset()

    alice_client = TestClient(app)
    alice_client.post("/login", data={"role": "enduser", "username": "alice", "password": "pw-alice"})

    grid = alice_client.get("/review/grid").json()
    assert len(grid["datasets"]) == 1
    ds_grid = grid["datasets"][0]
    assert ds_grid["dataset_id"] == ds_id
    row_indices = {row["row_index"] for row in ds_grid["rows"]}
    assert row_indices == {0, 1}  # only alice's rows, never bob's or the unassigned row

    row0 = next(r for r in ds_grid["rows"] if r["row_index"] == 0)
    name_cell = next(c for c in row0["cells"] if c["column_def_id"] == col_ids["Name"])
    assert name_cell["editable"] is True
    assert set(name_cell["options"]) == {"Alice", "Alicia"}

    city_cell = next(c for c in row0["cells"] if c["column_def_id"] == col_ids["City"])
    assert city_cell["editable"] is False

    # Autosave (POST /review/save) only persists — it must not touch the target table yet.
    save_resp = alice_client.post(
        "/review/save",
        json={"dataset_id": ds_id, "edits": [{"row_index": 0, "column_def_id": col_ids["Name"], "value": "Alice"}]},
    )
    assert save_resp.status_code == 200, save_resp.text
    assert save_resp.json() == {"saved": 1}

    with engine.connect() as conn:
        tables = {
            row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
    assert "corrected_flow" not in tables  # not shipped yet

    # Now alice explicitly ships.
    ship_resp = alice_client.post(f"/review/datasets/{ds_id}/ship")
    assert ship_resp.status_code == 200, ship_resp.text
    body = ship_resp.json()
    assert body["table_name"] == "corrected_flow"
    assert body["row_count"] == 4  # full dataset, not just alice's rows

    rows_after_alice = _target_table_rows()
    assert rows_after_alice[0][0] == "Alice"        # alice's correction landed
    assert rows_after_alice[2][1] == "unk"          # bob's row still raw, untouched

    # Tamper attempt: alice tries to edit bob's row.
    tamper_resp = alice_client.post(
        "/review/save",
        json={"dataset_id": ds_id, "edits": [{"row_index": 2, "column_def_id": col_ids["Status"], "value": "active"}]},
    )
    assert tamper_resp.status_code == 422
    rows_after_tamper = _target_table_rows()
    assert rows_after_tamper == rows_after_alice  # target table untouched by the rejected save

    bob_client = TestClient(app)
    bob_client.post("/login", data={"role": "enduser", "username": "bob", "password": "pw-bob"})

    bob_grid = bob_client.get("/review/grid").json()
    assert len(bob_grid["datasets"]) == 1
    assert {row["row_index"] for row in bob_grid["datasets"][0]["rows"]} == {2}

    bob_save = bob_client.post(
        "/review/save",
        json={"dataset_id": ds_id, "edits": [{"row_index": 2, "column_def_id": col_ids["Status"], "value": "active"}]},
    )
    assert bob_save.status_code == 200, bob_save.text

    # Bob's own ship publishes his change plus alice's earlier one — accumulation across users.
    bob_ship = bob_client.post(f"/review/datasets/{ds_id}/ship")
    assert bob_ship.status_code == 200, bob_ship.text

    rows_after_bob = _target_table_rows()
    assert rows_after_bob[0][0] == "Alice"   # alice's earlier save was not clobbered
    assert rows_after_bob[2][1] == "active"  # bob's correction landed
    assert rows_after_bob[3][0] == "Dana"    # unassigned row carried through untouched


def test_ship_rejected_for_enduser_with_no_rows_in_dataset():
    ds_id, col_ids = _setup_dataset(target_table="corrected_noaccess")

    admin_client = TestClient(app)
    admin_client.post("/login", data={"role": "master_admin", "password": "test-admin-pw"})
    outsider_resp = admin_client.post("/admin/endusers", json={"username": "eve", "password": "pw-eve"})
    assert outsider_resp.status_code == 201

    eve_client = TestClient(app)
    eve_client.post("/login", data={"role": "enduser", "username": "eve", "password": "pw-eve"})

    grid = eve_client.get("/review/grid").json()
    assert grid["datasets"] == []  # eve has no rows in any dataset

    resp = eve_client.post(f"/review/datasets/{ds_id}/ship")
    assert resp.status_code == 403


def test_end_user_grid_spans_multiple_datasets():
    ds1_id, col_ids_1 = _setup_dataset(target_table="corrected_multi_1", label="Dataset One")

    admin_client = TestClient(app)
    admin_client.post("/login", data={"role": "master_admin", "password": "test-admin-pw"})
    ds2_id, col_ids_2 = _ingest_sample(admin_client, label="Dataset Two")
    admin_client.put(
        f"/admin/datasets/{ds2_id}/exposed-columns",
        json={"column_def_ids": [col_ids_2["Name"], col_ids_2["Status"], col_ids_2["City"], col_ids_2["Amount"]]},
    )
    admin_client.put(f"/admin/datasets/{ds2_id}/target-table", json={"table_name": "corrected_multi_2"})
    # Reuse alice from dataset one's setup, assign her a row in dataset two as well.
    endusers = admin_client.get("/admin/endusers").json()
    alice_id = next(u["id"] for u in endusers if u["username"] == "alice")
    admin_client.put(f"/admin/datasets/{ds2_id}/rows/0/assign", json={"enduser_id": alice_id})

    alice_client = TestClient(app)
    alice_client.post("/login", data={"role": "enduser", "username": "alice", "password": "pw-alice"})

    grid = alice_client.get("/review/grid").json()
    dataset_ids = {d["dataset_id"] for d in grid["datasets"]}
    assert dataset_ids == {ds1_id, ds2_id}


def test_admin_added_columns_are_editable_and_save():
    ds_id, col_ids = _setup_dataset()

    admin_client = TestClient(app)
    admin_client.post("/login", data={"role": "master_admin", "password": "test-admin-pw"})

    dropdown_col = admin_client.post(
        f"/admin/datasets/{ds_id}/columns",
        json={"name": "Priority", "input_type": "dropdown", "options": ["High", "Low"]},
    ).json()
    text_col = admin_client.post(
        f"/admin/datasets/{ds_id}/columns", json={"name": "Comments", "input_type": "text", "options": None}
    ).json()

    alice_client = TestClient(app)
    alice_client.post("/login", data={"role": "enduser", "username": "alice", "password": "pw-alice"})

    grid = alice_client.get("/review/grid").json()
    ds_grid = grid["datasets"][0]
    row0 = next(r for r in ds_grid["rows"] if r["row_index"] == 0)

    priority_cell = next(c for c in row0["cells"] if c["column_def_id"] == dropdown_col["id"])
    assert priority_cell["editable"] is True
    assert priority_cell["input_type"] == "dropdown"
    assert set(priority_cell["options"]) == {"High", "Low"}
    assert priority_cell["value"] is None  # admin-added column starts blank

    comments_cell = next(c for c in row0["cells"] if c["column_def_id"] == text_col["id"])
    assert comments_cell["editable"] is True
    assert comments_cell["input_type"] == "text"

    # Dropdown value outside the admin-defined options is rejected.
    bad_resp = alice_client.post(
        "/review/save",
        json={"dataset_id": ds_id, "edits": [{"row_index": 0, "column_def_id": dropdown_col["id"], "value": "Medium"}]},
    )
    assert bad_resp.status_code == 422

    ok_resp = alice_client.post(
        "/review/save",
        json={
            "dataset_id": ds_id,
            "edits": [
                {"row_index": 0, "column_def_id": dropdown_col["id"], "value": "High"},
                {"row_index": 0, "column_def_id": text_col["id"], "value": "looks fine to me"},
            ],
        },
    )
    assert ok_resp.status_code == 200, ok_resp.text

    ship_resp = alice_client.post(f"/review/datasets/{ds_id}/ship")
    assert ship_resp.status_code == 200, ship_resp.text

    with engine.connect() as conn:
        row = conn.execute(
            text(
                f'SELECT "{dropdown_col["safe_name"]}", "{text_col["safe_name"]}" '
                'FROM "corrected_flow" WHERE id = 1'
            )
        ).fetchone()
    assert row[0] == "High"
    assert row[1] == "looks fine to me"

    # Free text past the length cap is rejected.
    too_long_resp = alice_client.post(
        "/review/save",
        json={"dataset_id": ds_id, "edits": [{"row_index": 0, "column_def_id": text_col["id"], "value": "x" * 501}]},
    )
    assert too_long_resp.status_code == 422

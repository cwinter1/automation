import pytest
from sqlalchemy import text

from app.db import engine
from app.models import CellEditRule, ColumnDef, Dataset, EndUser, RawRow, TargetTableSetting
from app.target import (
    EditRequest,
    NotConfiguredError,
    ValidationError,
    apply_enduser_edits,
    build_corrected_rows,
    create_or_replace_target_table,
    ship_dataset_to_db,
)


def _seed(db_session, target_table="corrected_test"):
    dataset = Dataset(source_type="xlsx", label="Test dataset")
    db_session.add(dataset)
    db_session.flush()

    col_name = ColumnDef(dataset_id=dataset.id, source_name="Name", safe_name="name", order_index=0)
    col_status = ColumnDef(dataset_id=dataset.id, source_name="Status", safe_name="status", order_index=1)
    db_session.add_all([col_name, col_status])
    db_session.flush()

    alice = EndUser(username="alice", password_hash="x")
    bob = EndUser(username="bob", password_hash="x")
    db_session.add_all([alice, bob])
    db_session.flush()

    rows = [
        RawRow(dataset_id=dataset.id, row_index=0, data={"name": "Alise", "status": "ok"}, assigned_enduser_id=alice.id),
        RawRow(dataset_id=dataset.id, row_index=1, data={"name": "Bob", "status": "unk"}, assigned_enduser_id=bob.id),
        RawRow(dataset_id=dataset.id, row_index=2, data={"name": "Carl", "status": "ok"}, assigned_enduser_id=None),
    ]
    db_session.add_all(rows)
    db_session.flush()

    rule_a = CellEditRule(
        dataset_id=dataset.id, row_index=0, column_def_id=col_name.id, options=["Alice", "Alicia"]
    )
    rule_b = CellEditRule(
        dataset_id=dataset.id, row_index=1, column_def_id=col_status.id, options=["active", "inactive"]
    )
    db_session.add_all([rule_a, rule_b])

    if target_table:
        db_session.add(TargetTableSetting(dataset_id=dataset.id, table_name=target_table))

    db_session.commit()
    return dataset, col_name, col_status, alice, bob


def test_build_corrected_rows_uses_raw_values_when_no_edits(db_session):
    dataset, col_name, col_status, alice, bob = _seed(db_session)

    columns, rows = build_corrected_rows(db_session, dataset)

    assert [c.safe_name for c in columns] == ["name", "status"]
    assert rows[0] == {"name": "Alise", "status": "ok"}
    assert rows[1] == {"name": "Bob", "status": "unk"}
    assert rows[2] == {"name": "Carl", "status": "ok"}


def test_apply_edits_rejects_edit_on_row_not_owned_by_caller(db_session):
    dataset, col_name, col_status, alice, bob = _seed(db_session)

    edits = [EditRequest(row_index=1, column_def_id=col_status.id, value="active")]
    with pytest.raises(ValidationError):
        apply_enduser_edits(db_session, dataset, alice.id, edits)  # row 1 belongs to bob


def test_apply_edits_rejects_edit_on_unflagged_cell(db_session):
    dataset, col_name, col_status, alice, bob = _seed(db_session)

    edits = [EditRequest(row_index=0, column_def_id=col_status.id, value="ok")]
    with pytest.raises(ValidationError):
        apply_enduser_edits(db_session, dataset, alice.id, edits)  # (row0, status) not flagged


def test_apply_edits_rejects_value_outside_options(db_session):
    dataset, col_name, col_status, alice, bob = _seed(db_session)

    edits = [EditRequest(row_index=0, column_def_id=col_name.id, value="Not An Option")]
    with pytest.raises(ValidationError):
        apply_enduser_edits(db_session, dataset, alice.id, edits)


def test_apply_edits_persists_without_shipping(db_session):
    dataset, col_name, col_status, alice, bob = _seed(db_session)

    edits = [EditRequest(row_index=0, column_def_id=col_name.id, value="Alice")]
    apply_enduser_edits(db_session, dataset, alice.id, edits)

    # Persisted for the next build, but the target table hasn't been touched yet.
    columns, rows = build_corrected_rows(db_session, dataset)
    assert rows[0]["name"] == "Alice"

    tables = _sqlite_master_names()
    assert "corrected_test" not in tables


def test_ship_requires_target_table_configured(db_session):
    dataset, col_name, col_status, alice, bob = _seed(db_session, target_table=None)

    with pytest.raises(NotConfiguredError):
        ship_dataset_to_db(db_session, dataset)


def test_create_or_replace_target_table_rejects_malicious_name(db_session):
    dataset, col_name, col_status, alice, bob = _seed(db_session)
    columns, _ = build_corrected_rows(db_session, dataset)

    before = _sqlite_master_names()
    with engine.begin() as conn:
        with pytest.raises(ValueError):
            create_or_replace_target_table(conn, "x; DROP TABLE end_users;--", columns)
    after = _sqlite_master_names()
    assert before == after


def test_cross_enduser_saves_accumulate_without_clobbering(db_session):
    dataset, col_name, col_status, alice, bob = _seed(db_session, target_table="corrected_multi")

    apply_enduser_edits(
        db_session, dataset, alice.id, [EditRequest(row_index=0, column_def_id=col_name.id, value="Alice")]
    )
    result_a = ship_dataset_to_db(db_session, dataset)
    assert result_a.row_count == 3

    with engine.connect() as conn:
        rows_after_a = conn.execute(text('SELECT name, status FROM "corrected_multi" ORDER BY id')).fetchall()
    assert rows_after_a[0][0] == "Alice"  # alice's correction landed
    assert rows_after_a[1][0] == "Bob"    # bob's row untouched, still raw

    apply_enduser_edits(
        db_session, dataset, bob.id, [EditRequest(row_index=1, column_def_id=col_status.id, value="active")]
    )
    result_b = ship_dataset_to_db(db_session, dataset)
    assert result_b.row_count == 3

    with engine.connect() as conn:
        rows_after_b = conn.execute(text('SELECT name, status FROM "corrected_multi" ORDER BY id')).fetchall()

    # Bob's ship must not have wiped out Alice's earlier, already-shipped correction.
    assert rows_after_b[0][0] == "Alice"
    assert rows_after_b[1][1] == "active"
    assert rows_after_b[2][0] == "Carl"


def test_ship_handles_source_column_named_id(db_session):
    dataset = Dataset(source_type="xlsx", label="Id collision dataset")
    db_session.add(dataset)
    db_session.flush()

    col_id = ColumnDef(dataset_id=dataset.id, source_name="ID", safe_name="id", order_index=0)
    col_name = ColumnDef(dataset_id=dataset.id, source_name="Name", safe_name="name", order_index=1)
    db_session.add_all([col_id, col_name])
    db_session.flush()

    db_session.add(RawRow(dataset_id=dataset.id, row_index=0, data={"id": "SRC-1", "name": "Alice"}))
    db_session.add(TargetTableSetting(dataset_id=dataset.id, table_name="corrected_id_collision"))
    db_session.commit()

    result = ship_dataset_to_db(db_session, dataset)
    assert result.row_count == 1

    with engine.connect() as conn:
        rows = conn.execute(text('SELECT id, name FROM "corrected_id_collision"')).fetchall()
    assert rows == [("SRC-1", "Alice")]


def _sqlite_master_names():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        return {row[0] for row in result}

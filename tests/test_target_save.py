import pytest
from sqlalchemy import inspect, text

from app.db import engine
from app.models import CellEditRule, ColumnDef, Dataset, EndUser, RawRow, TargetTableSetting
from app.target import (
    EditRequest,
    NotConfiguredError,
    ValidationError,
    build_corrected_rows,
    create_or_replace_target_table,
    save_corrected_dataset,
)


def _seed(db_session, target_table="corrected_test"):
    dataset = Dataset(source_type="xlsx")
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


def test_save_rejects_edit_on_row_not_owned_by_caller(db_session):
    dataset, col_name, col_status, alice, bob = _seed(db_session)

    edits = [EditRequest(row_index=1, column_def_id=col_status.id, value="active")]
    with pytest.raises(ValidationError):
        save_corrected_dataset(db_session, dataset, alice.id, edits)  # row 1 belongs to bob


def test_save_rejects_edit_on_unflagged_cell(db_session):
    dataset, col_name, col_status, alice, bob = _seed(db_session)

    edits = [EditRequest(row_index=0, column_def_id=col_status.id, value="ok")]
    with pytest.raises(ValidationError):
        save_corrected_dataset(db_session, dataset, alice.id, edits)  # (row0, status) not flagged


def test_save_rejects_value_outside_options(db_session):
    dataset, col_name, col_status, alice, bob = _seed(db_session)

    edits = [EditRequest(row_index=0, column_def_id=col_name.id, value="Not An Option")]
    with pytest.raises(ValidationError):
        save_corrected_dataset(db_session, dataset, alice.id, edits)


def test_save_requires_target_table_configured(db_session):
    dataset, col_name, col_status, alice, bob = _seed(db_session, target_table=None)

    with pytest.raises(NotConfiguredError):
        save_corrected_dataset(db_session, dataset, alice.id, [])


def test_create_or_replace_target_table_rejects_malicious_name(db_session):
    dataset, col_name, col_status, alice, bob = _seed(db_session)
    _, columns_rows = (None, None)
    columns, _ = build_corrected_rows(db_session, dataset)

    before = _sqlite_master_names()
    with engine.begin() as conn:
        with pytest.raises(ValueError):
            create_or_replace_target_table(conn, "x; DROP TABLE end_users;--", columns)
    after = _sqlite_master_names()
    assert before == after


def test_cross_enduser_saves_accumulate_without_clobbering(db_session):
    dataset, col_name, col_status, alice, bob = _seed(db_session, target_table="corrected_multi")

    result_a = save_corrected_dataset(
        db_session, dataset, alice.id, [EditRequest(row_index=0, column_def_id=col_name.id, value="Alice")]
    )
    assert result_a.row_count == 3

    with engine.connect() as conn:
        rows_after_a = conn.execute(text('SELECT name, status FROM "corrected_multi" ORDER BY id')).fetchall()
    assert rows_after_a[0][0] == "Alice"  # alice's correction landed
    assert rows_after_a[1][0] == "Bob"    # bob's row untouched, still raw

    result_b = save_corrected_dataset(
        db_session, dataset, bob.id, [EditRequest(row_index=1, column_def_id=col_status.id, value="active")]
    )
    assert result_b.row_count == 3

    with engine.connect() as conn:
        rows_after_b = conn.execute(text('SELECT name, status FROM "corrected_multi" ORDER BY id')).fetchall()

    # Bob's save must not have wiped out Alice's earlier, already-saved correction.
    assert rows_after_b[0][0] == "Alice"
    assert rows_after_b[1][1] == "active"
    assert rows_after_b[2][0] == "Carl"


def _sqlite_master_names():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        return {row[0] for row in result}

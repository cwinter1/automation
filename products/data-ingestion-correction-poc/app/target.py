from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.db import engine
from app.models import CellEditRule, CellEditValue, ColumnDef, Dataset, RawRow, TargetTableSetting
from app.sanitize import validate_identifier


class ValidationError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class NotConfiguredError(Exception):
    pass


MAX_FREE_TEXT_LENGTH = 500


@dataclass
class EditRequest:
    row_index: int
    column_def_id: int
    value: str


@dataclass
class SaveResult:
    table_name: str
    row_count: int


def _load_cell_rules(db: Session, dataset_id: int) -> dict[tuple[int, int], list[str]]:
    rules = db.query(CellEditRule).filter(CellEditRule.dataset_id == dataset_id).all()
    return {(r.row_index, r.column_def_id): r.options for r in rules}


def apply_enduser_edits(db: Session, dataset: Dataset, enduser_id: int, edits: list[EditRequest]) -> None:
    """Validate ownership + editability + value validity, then upsert CellEditValue rows.

    A cell is editable one of two ways: an ingested column with a per-cell CellEditRule
    (value must be in that rule's options), or an admin-added column (always editable for
    an assigned row; dropdown-type requires value in the column's options, text-type accepts
    any string up to MAX_FREE_TEXT_LENGTH). Raises ValidationError (caller returns 422) if any
    submitted edit targets a row not assigned to this end user or fails these checks —
    defends against a tampered request body, not just a buggy client.
    """
    if not edits:
        return

    row_owner = {
        r.row_index: r.assigned_enduser_id
        for r in db.query(RawRow).filter(RawRow.dataset_id == dataset.id).all()
    }
    cell_rules = _load_cell_rules(db, dataset.id)
    admin_columns = {
        c.id: c
        for c in db.query(ColumnDef).filter(
            ColumnDef.dataset_id == dataset.id, ColumnDef.is_admin_added.is_(True)
        )
    }

    errors = []
    valid_edits = []
    for edit in edits:
        owner = row_owner.get(edit.row_index)
        if owner is None or owner != enduser_id:
            errors.append(f"Row {edit.row_index} is not assigned to you")
            continue

        admin_col = admin_columns.get(edit.column_def_id)
        if admin_col is not None:
            if admin_col.input_type == "dropdown":
                if edit.value not in (admin_col.options or []):
                    errors.append(
                        f"Value {edit.value!r} is not a valid option for row {edit.row_index}, "
                        f"column {edit.column_def_id}"
                    )
                    continue
            elif len(edit.value) > MAX_FREE_TEXT_LENGTH:
                errors.append(
                    f"Value for row {edit.row_index}, column {edit.column_def_id} exceeds "
                    f"{MAX_FREE_TEXT_LENGTH} characters"
                )
                continue
            valid_edits.append(edit)
            continue

        options = cell_rules.get((edit.row_index, edit.column_def_id))
        if options is None:
            errors.append(f"Cell (row {edit.row_index}, column {edit.column_def_id}) is not editable")
            continue
        if edit.value not in options:
            errors.append(
                f"Value {edit.value!r} is not a valid option for row {edit.row_index}, "
                f"column {edit.column_def_id}"
            )
            continue
        valid_edits.append(edit)

    if errors:
        raise ValidationError(errors)

    for edit in valid_edits:
        existing = (
            db.query(CellEditValue)
            .filter(
                CellEditValue.dataset_id == dataset.id,
                CellEditValue.row_index == edit.row_index,
                CellEditValue.column_def_id == edit.column_def_id,
            )
            .first()
        )
        if existing:
            existing.value = edit.value
            existing.edited_by_enduser_id = enduser_id
        else:
            db.add(
                CellEditValue(
                    dataset_id=dataset.id,
                    row_index=edit.row_index,
                    column_def_id=edit.column_def_id,
                    value=edit.value,
                    edited_by_enduser_id=enduser_id,
                )
            )
    db.commit()


def build_corrected_rows(db: Session, dataset: Dataset) -> tuple[list[ColumnDef], list[dict]]:
    """Merge raw data with every persisted CellEditValue (across all end users)."""
    columns = (
        db.query(ColumnDef)
        .filter(ColumnDef.dataset_id == dataset.id)
        .order_by(ColumnDef.order_index)
        .all()
    )
    raw_rows = (
        db.query(RawRow)
        .filter(RawRow.dataset_id == dataset.id)
        .order_by(RawRow.row_index)
        .all()
    )
    edit_values = db.query(CellEditValue).filter(CellEditValue.dataset_id == dataset.id).all()
    edit_map = {(e.row_index, e.column_def_id): e.value for e in edit_values}

    corrected = []
    for row in raw_rows:
        record = {}
        for col in columns:
            override = edit_map.get((row.row_index, col.id))
            record[col.safe_name] = override if override is not None else row.data.get(col.safe_name)
        corrected.append(record)

    return columns, corrected


def _surrogate_pk_name(columns: list[ColumnDef]) -> str:
    """A synthetic primary-key column name guaranteed not to collide with any
    ColumnDef.safe_name (e.g. a source column literally named "id")."""
    taken = {c.safe_name for c in columns}
    candidate = "id"
    suffix = 2
    while candidate in taken:
        candidate = f"id_{suffix}"
        suffix += 1
    return candidate


def create_or_replace_target_table(conn: Connection, table_name: str, columns: list[ColumnDef]) -> None:
    validate_identifier(table_name)
    for col in columns:
        validate_identifier(col.safe_name)

    pk_name = _surrogate_pk_name(columns)
    col_sql = ", ".join(f'"{c.safe_name}" TEXT' for c in columns)
    conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
    conn.execute(text(f'CREATE TABLE "{table_name}" ("{pk_name}" INTEGER PRIMARY KEY AUTOINCREMENT, {col_sql})'))


def insert_corrected_rows(conn: Connection, table_name: str, columns: list[ColumnDef], rows: list[dict]) -> int:
    validate_identifier(table_name)
    if not rows:
        return 0

    col_list = ", ".join(f'"{c.safe_name}"' for c in columns)
    placeholders = ", ".join(f":{c.safe_name}" for c in columns)
    stmt = text(f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders})')
    conn.execute(stmt, rows)
    return len(rows)


def ship_dataset_to_db(db: Session, dataset: Dataset) -> SaveResult:
    """Publish the dataset's current state (raw data + every persisted CellEditValue,
    across all end users) into its target table. This is the explicit "Ship to DB" action —
    distinct from apply_enduser_edits, which just persists an edit so it isn't lost. Autosave
    calls apply_enduser_edits only; this function is only called when an end user or admin
    explicitly ships the dataset.
    """
    setting = (
        db.query(TargetTableSetting)
        .filter(TargetTableSetting.dataset_id == dataset.id)
        .first()
    )
    if setting is None:
        raise NotConfiguredError("Target table has not been configured by the admin")

    columns, rows = build_corrected_rows(db, dataset)

    with engine.begin() as conn:
        create_or_replace_target_table(conn, setting.table_name, columns)
        row_count = insert_corrected_rows(conn, setting.table_name, columns, rows)

    return SaveResult(table_name=setting.table_name, row_count=row_count)

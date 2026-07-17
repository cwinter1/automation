from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import hash_password, require_admin, require_admin_page
from app.db import get_db
from app.ingestion import make_safe_identifier, parse_xlsx, pull_from_db, replace_active_dataset
from app.models import CellEditRule, ColumnDef, Dataset, EndUser, ExposedColumn, RawRow, TargetTableSetting
from app.sanitize import validate_identifier
from app.schemas import (
    AdminColumnIn,
    AdminDatasetResponse,
    CellRuleIn,
    CellRuleOut,
    ColumnOut,
    EndUserIn,
    EndUserOut,
    ExposedColumnOut,
    ExposedColumnsIn,
    IngestDbRequest,
    IngestResponse,
    RawRowOut,
    RowAssignBulkIn,
    RowAssignBulkOut,
    RowAssignIn,
    TargetTableIn,
    TargetTableOut,
)

templates = Jinja2Templates(directory="app/templates")

pages_router = APIRouter(dependencies=[Depends(require_admin_page)])
api_router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


@pages_router.get("/admin")
def admin_page(request: Request):
    return templates.TemplateResponse(request, "admin.html", {})


def _get_active_dataset(db: Session) -> Dataset:
    dataset = db.query(Dataset).filter(Dataset.is_active.is_(True)).first()
    if dataset is None:
        raise HTTPException(status_code=400, detail="No dataset has been ingested yet")
    return dataset


def _ingest_response(dataset: Dataset, db: Session) -> IngestResponse:
    columns = (
        db.query(ColumnDef)
        .filter(ColumnDef.dataset_id == dataset.id)
        .order_by(ColumnDef.order_index)
        .all()
    )
    row_count = db.query(RawRow).filter(RawRow.dataset_id == dataset.id).count()
    return IngestResponse(
        dataset_id=dataset.id,
        columns=[ColumnOut.model_validate(c, from_attributes=True) for c in columns],
        row_count=row_count,
    )


@api_router.post("/ingest/xlsx", response_model=IngestResponse)
async def ingest_xlsx(file: UploadFile, db: Session = Depends(get_db)):
    content = await file.read()
    try:
        columns, rows = parse_xlsx(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    dataset = replace_active_dataset(db, "xlsx", columns, rows)
    return _ingest_response(dataset, db)


@api_router.post("/ingest/db", response_model=IngestResponse)
def ingest_db(payload: IngestDbRequest, db: Session = Depends(get_db)):
    try:
        columns, rows = pull_from_db(payload.connection_string, payload.table_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    dataset = replace_active_dataset(db, "db", columns, rows)
    return _ingest_response(dataset, db)


@api_router.get("/dataset", response_model=AdminDatasetResponse)
def get_dataset(db: Session = Depends(get_db)):
    dataset = _get_active_dataset(db)
    columns = (
        db.query(ColumnDef)
        .filter(ColumnDef.dataset_id == dataset.id)
        .order_by(ColumnDef.order_index)
        .all()
    )
    rows = (
        db.query(RawRow)
        .filter(RawRow.dataset_id == dataset.id)
        .order_by(RawRow.row_index)
        .all()
    )
    return AdminDatasetResponse(
        dataset_id=dataset.id,
        columns=[ColumnOut.model_validate(c, from_attributes=True) for c in columns],
        rows=[
            RawRowOut(row_index=r.row_index, values=r.data, assigned_enduser_id=r.assigned_enduser_id)
            for r in rows
        ],
    )


@api_router.post("/columns", response_model=ColumnOut, status_code=201)
def create_admin_column(payload: AdminColumnIn, db: Session = Depends(get_db)):
    dataset = _get_active_dataset(db)

    if payload.input_type not in ("dropdown", "text"):
        raise HTTPException(status_code=400, detail="input_type must be 'dropdown' or 'text'")
    if payload.input_type == "dropdown" and (not payload.options or len(payload.options) < 2):
        raise HTTPException(status_code=400, detail="Dropdown columns need at least 2 options")

    existing_safe_names = {
        c.safe_name for c in db.query(ColumnDef).filter(ColumnDef.dataset_id == dataset.id).all()
    }
    safe_name = make_safe_identifier(payload.name, existing_safe_names)
    max_order = (
        db.query(func.max(ColumnDef.order_index)).filter(ColumnDef.dataset_id == dataset.id).scalar()
    )

    column = ColumnDef(
        dataset_id=dataset.id,
        source_name=payload.name,
        safe_name=safe_name,
        order_index=(max_order if max_order is not None else -1) + 1,
        is_admin_added=True,
        input_type=payload.input_type,
        options=payload.options if payload.input_type == "dropdown" else None,
    )
    db.add(column)
    db.commit()
    db.refresh(column)
    return ColumnOut.model_validate(column, from_attributes=True)


@api_router.delete("/columns/{column_def_id}", status_code=204)
def delete_admin_column(column_def_id: int, db: Session = Depends(get_db)):
    dataset = _get_active_dataset(db)
    column = (
        db.query(ColumnDef)
        .filter(ColumnDef.dataset_id == dataset.id, ColumnDef.id == column_def_id)
        .first()
    )
    if column is None:
        raise HTTPException(status_code=404, detail="Column not found")
    if not column.is_admin_added:
        raise HTTPException(status_code=400, detail="Only admin-added columns can be deleted")
    db.delete(column)
    db.commit()


@api_router.get("/exposed-columns", response_model=list[ExposedColumnOut])
def get_exposed_columns(db: Session = Depends(get_db)):
    dataset = _get_active_dataset(db)
    exposed = (
        db.query(ExposedColumn, ColumnDef)
        .join(ColumnDef, ExposedColumn.column_def_id == ColumnDef.id)
        .filter(ExposedColumn.dataset_id == dataset.id)
        .order_by(ExposedColumn.display_order)
        .all()
    )
    return [
        ExposedColumnOut(column_def_id=col.id, source_name=col.source_name, display_order=exp.display_order)
        for exp, col in exposed
    ]


@api_router.put("/exposed-columns", status_code=204)
def set_exposed_columns(payload: ExposedColumnsIn, db: Session = Depends(get_db)):
    dataset = _get_active_dataset(db)
    valid_ids = {
        c.id for c in db.query(ColumnDef).filter(ColumnDef.dataset_id == dataset.id).all()
    }
    if not set(payload.column_def_ids).issubset(valid_ids):
        raise HTTPException(status_code=400, detail="Unknown column_def_id for the active dataset")
    if len(set(payload.column_def_ids)) != len(payload.column_def_ids):
        raise HTTPException(status_code=400, detail="Duplicate column_def_ids")

    db.query(ExposedColumn).filter(ExposedColumn.dataset_id == dataset.id).delete()
    for idx, col_id in enumerate(payload.column_def_ids):
        db.add(ExposedColumn(dataset_id=dataset.id, column_def_id=col_id, display_order=idx))
    db.commit()


@api_router.get("/target-table", response_model=TargetTableOut)
def get_target_table(db: Session = Depends(get_db)):
    dataset = _get_active_dataset(db)
    setting = db.query(TargetTableSetting).filter(TargetTableSetting.dataset_id == dataset.id).first()
    return TargetTableOut(table_name=setting.table_name if setting else None)


@api_router.put("/target-table", status_code=204)
def set_target_table(payload: TargetTableIn, db: Session = Depends(get_db)):
    dataset = _get_active_dataset(db)
    try:
        validate_identifier(payload.table_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    setting = db.query(TargetTableSetting).filter(TargetTableSetting.dataset_id == dataset.id).first()
    if setting is None:
        db.add(TargetTableSetting(dataset_id=dataset.id, table_name=payload.table_name))
    else:
        setting.table_name = payload.table_name
    db.commit()


@api_router.get("/cell-rules", response_model=list[CellRuleOut])
def get_cell_rules(db: Session = Depends(get_db)):
    dataset = _get_active_dataset(db)
    rules = db.query(CellEditRule).filter(CellEditRule.dataset_id == dataset.id).all()
    return [
        CellRuleOut(row_index=r.row_index, column_def_id=r.column_def_id, options=r.options) for r in rules
    ]


@api_router.put("/cell-rules/{row_index}/{column_def_id}", status_code=204)
def set_cell_rule(row_index: int, column_def_id: int, payload: CellRuleIn, db: Session = Depends(get_db)):
    dataset = _get_active_dataset(db)

    exposed = (
        db.query(ExposedColumn)
        .filter(ExposedColumn.dataset_id == dataset.id, ExposedColumn.column_def_id == column_def_id)
        .first()
    )
    if exposed is None:
        raise HTTPException(status_code=400, detail="Column must be exposed before it can be flagged")

    row_exists = (
        db.query(RawRow)
        .filter(RawRow.dataset_id == dataset.id, RawRow.row_index == row_index)
        .first()
    )
    if row_exists is None:
        raise HTTPException(status_code=404, detail="Row not found")

    rule = (
        db.query(CellEditRule)
        .filter(
            CellEditRule.dataset_id == dataset.id,
            CellEditRule.row_index == row_index,
            CellEditRule.column_def_id == column_def_id,
        )
        .first()
    )
    if rule is None:
        db.add(
            CellEditRule(
                dataset_id=dataset.id,
                row_index=row_index,
                column_def_id=column_def_id,
                options=payload.options,
            )
        )
    else:
        rule.options = payload.options
    db.commit()


@api_router.delete("/cell-rules/{row_index}/{column_def_id}", status_code=204)
def delete_cell_rule(row_index: int, column_def_id: int, db: Session = Depends(get_db)):
    dataset = _get_active_dataset(db)
    db.query(CellEditRule).filter(
        CellEditRule.dataset_id == dataset.id,
        CellEditRule.row_index == row_index,
        CellEditRule.column_def_id == column_def_id,
    ).delete()
    db.commit()


@api_router.get("/endusers", response_model=list[EndUserOut])
def list_endusers(db: Session = Depends(get_db)):
    users = db.query(EndUser).order_by(EndUser.username).all()
    return [EndUserOut(id=u.id, username=u.username) for u in users]


@api_router.post("/endusers", response_model=EndUserOut, status_code=201)
def create_enduser(payload: EndUserIn, db: Session = Depends(get_db)):
    existing = db.query(EndUser).filter(EndUser.username == payload.username).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already exists")
    user = EndUser(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return EndUserOut(id=user.id, username=user.username)


@api_router.delete("/endusers/{enduser_id}", status_code=204)
def delete_enduser(enduser_id: int, db: Session = Depends(get_db)):
    user = db.query(EndUser).filter(EndUser.id == enduser_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="End user not found")
    db.delete(user)
    db.commit()


@api_router.put("/rows/{row_index}/assign", status_code=204)
def assign_row(row_index: int, payload: RowAssignIn, db: Session = Depends(get_db)):
    dataset = _get_active_dataset(db)
    row = (
        db.query(RawRow)
        .filter(RawRow.dataset_id == dataset.id, RawRow.row_index == row_index)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Row not found")

    if payload.enduser_id is not None:
        user = db.query(EndUser).filter(EndUser.id == payload.enduser_id).first()
        if user is None:
            raise HTTPException(status_code=400, detail="Unknown enduser_id")

    row.assigned_enduser_id = payload.enduser_id
    db.commit()


@api_router.put("/rows/assign-bulk", response_model=RowAssignBulkOut)
def assign_rows_bulk(payload: RowAssignBulkIn, db: Session = Depends(get_db)):
    dataset = _get_active_dataset(db)

    if payload.enduser_id is not None:
        user = db.query(EndUser).filter(EndUser.id == payload.enduser_id).first()
        if user is None:
            raise HTTPException(status_code=400, detail="Unknown enduser_id")

    requested = set(payload.row_indices)
    found = {
        r.row_index
        for r in db.query(RawRow.row_index).filter(
            RawRow.dataset_id == dataset.id, RawRow.row_index.in_(requested)
        )
    }
    missing = requested - found
    if missing:
        raise HTTPException(status_code=404, detail=f"Rows not found: {sorted(missing)}")

    updated = (
        db.query(RawRow)
        .filter(RawRow.dataset_id == dataset.id, RawRow.row_index.in_(requested))
        .update({"assigned_enduser_id": payload.enduser_id}, synchronize_session=False)
    )
    db.commit()
    return RowAssignBulkOut(updated=updated)


router = APIRouter()
router.include_router(pages_router)
router.include_router(api_router)

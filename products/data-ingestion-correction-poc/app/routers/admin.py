from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import hash_password, require_admin, require_admin_page, require_master_admin
from app.connections import get_connection_names
from app.db import get_db
from app.ingestion import create_new_dataset, make_safe_identifier, parse_xlsx, pull_from_db
from app.models import AdminUser, CellEditRule, ColumnDef, Dataset, EndUser, ExposedColumn, RawRow, TargetTableSetting
from app.sanitize import validate_identifier
from app.schemas import (
    AdminColumnIn,
    AdminDatasetResponse,
    AdminUserIn,
    AdminUserOut,
    CellRuleIn,
    CellRuleOut,
    ColumnOut,
    ConnectionNamesOut,
    DatasetMetadataOut,
    DatasetOut,
    EndUserIn,
    EndUserOut,
    ExposedColumnOut,
    ExposedColumnsIn,
    IngestDbRequest,
    IngestResponse,
    MetadataColumn,
    RawRowOut,
    RowAssignBulkIn,
    RowAssignBulkOut,
    RowAssignIn,
    ShipResponse,
    TargetTableIn,
    TargetTableOut,
)
from app.target import NotConfiguredError, ship_dataset_to_db

templates = Jinja2Templates(directory="app/templates")

pages_router = APIRouter(dependencies=[Depends(require_admin_page)])
api_router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
master_router = APIRouter(prefix="/admin", dependencies=[Depends(require_master_admin)])


@pages_router.get("/admin")
def admin_page(request: Request):
    return templates.TemplateResponse(request, "admin.html", {"role": request.session.get("role")})


def _get_dataset(db: Session, dataset_id: int) -> Dataset:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
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
        label=dataset.label,
        columns=[ColumnOut.model_validate(c, from_attributes=True) for c in columns],
        row_count=row_count,
    )


@api_router.get("/datasets", response_model=list[DatasetOut])
def list_datasets(db: Session = Depends(get_db)):
    datasets = db.query(Dataset).order_by(Dataset.created_at.desc()).all()
    out = []
    for ds in datasets:
        row_count = db.query(RawRow).filter(RawRow.dataset_id == ds.id).count()
        column_count = db.query(ColumnDef).filter(ColumnDef.dataset_id == ds.id).count()
        setting = db.query(TargetTableSetting).filter(TargetTableSetting.dataset_id == ds.id).first()
        out.append(
            DatasetOut(
                id=ds.id,
                label=ds.label,
                source_type=ds.source_type,
                row_count=row_count,
                column_count=column_count,
                target_table_name=setting.table_name if setting else None,
            )
        )
    return out


@api_router.get("/db-connections", response_model=ConnectionNamesOut)
def db_connections():
    return ConnectionNamesOut(names=get_connection_names())


@api_router.post("/ingest/xlsx", response_model=IngestResponse)
async def ingest_xlsx(file: UploadFile, label: str | None = None, db: Session = Depends(get_db)):
    content = await file.read()
    try:
        columns, rows = parse_xlsx(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    dataset = create_new_dataset(db, "xlsx", columns, rows, label=label)
    return _ingest_response(dataset, db)


@api_router.post("/ingest/db", response_model=IngestResponse)
def ingest_db(payload: IngestDbRequest, db: Session = Depends(get_db)):
    try:
        columns, rows = pull_from_db(payload.connection, payload.table_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    dataset = create_new_dataset(db, "db", columns, rows, label=payload.label)
    return _ingest_response(dataset, db)


@api_router.get("/datasets/{dataset_id}", response_model=AdminDatasetResponse)
def get_dataset(dataset_id: int, db: Session = Depends(get_db)):
    dataset = _get_dataset(db, dataset_id)
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
        label=dataset.label,
        columns=[ColumnOut.model_validate(c, from_attributes=True) for c in columns],
        rows=[
            RawRowOut(
                row_index=r.row_index,
                values=r.data,
                assigned_enduser_id=r.assigned_enduser_id,
                is_admin_added=r.is_admin_added,
            )
            for r in rows
        ],
    )


@api_router.get("/datasets/{dataset_id}/metadata", response_model=DatasetMetadataOut)
def get_dataset_metadata(dataset_id: int, db: Session = Depends(get_db)):
    dataset = _get_dataset(db, dataset_id)
    columns = (
        db.query(ColumnDef)
        .filter(ColumnDef.dataset_id == dataset.id)
        .order_by(ColumnDef.order_index)
        .all()
    )
    row_count = db.query(RawRow).filter(RawRow.dataset_id == dataset.id).count()
    setting = db.query(TargetTableSetting).filter(TargetTableSetting.dataset_id == dataset.id).first()

    # Every ColumnDef ends up as a column in the target table on ship (see
    # target.py::build_corrected_rows), so input and output columns are the same set today.
    metadata_columns = [
        MetadataColumn(source_name=c.source_name, safe_name=c.safe_name, is_admin_added=c.is_admin_added)
        for c in columns
    ]
    return DatasetMetadataOut(
        dataset_id=dataset.id,
        label=dataset.label,
        source_type=dataset.source_type,
        row_count=row_count,
        input_columns=metadata_columns,
        target_table_name=setting.table_name if setting else None,
        output_columns=metadata_columns,
    )


@api_router.post("/datasets/{dataset_id}/ship", response_model=ShipResponse)
def ship_dataset(dataset_id: int, db: Session = Depends(get_db)):
    dataset = _get_dataset(db, dataset_id)
    try:
        result = ship_dataset_to_db(db, dataset)
    except NotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return ShipResponse(table_name=result.table_name, row_count=result.row_count)


@api_router.post("/datasets/{dataset_id}/columns", response_model=ColumnOut, status_code=201)
def create_admin_column(dataset_id: int, payload: AdminColumnIn, db: Session = Depends(get_db)):
    dataset = _get_dataset(db, dataset_id)

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


@api_router.delete("/datasets/{dataset_id}/columns/{column_def_id}", status_code=204)
def delete_admin_column(dataset_id: int, column_def_id: int, db: Session = Depends(get_db)):
    dataset = _get_dataset(db, dataset_id)
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


@api_router.post("/datasets/{dataset_id}/rows", response_model=RawRowOut, status_code=201)
def create_admin_row(dataset_id: int, db: Session = Depends(get_db)):
    dataset = _get_dataset(db, dataset_id)
    max_row_index = (
        db.query(func.max(RawRow.row_index)).filter(RawRow.dataset_id == dataset.id).scalar()
    )
    row = RawRow(
        dataset_id=dataset.id,
        row_index=(max_row_index if max_row_index is not None else -1) + 1,
        data={},
        is_admin_added=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return RawRowOut(
        row_index=row.row_index,
        values=row.data,
        assigned_enduser_id=row.assigned_enduser_id,
        is_admin_added=row.is_admin_added,
    )


@api_router.get("/datasets/{dataset_id}/exposed-columns", response_model=list[ExposedColumnOut])
def get_exposed_columns(dataset_id: int, db: Session = Depends(get_db)):
    dataset = _get_dataset(db, dataset_id)
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


@api_router.put("/datasets/{dataset_id}/exposed-columns", status_code=204)
def set_exposed_columns(dataset_id: int, payload: ExposedColumnsIn, db: Session = Depends(get_db)):
    dataset = _get_dataset(db, dataset_id)
    valid_ids = {
        c.id for c in db.query(ColumnDef).filter(ColumnDef.dataset_id == dataset.id).all()
    }
    if not set(payload.column_def_ids).issubset(valid_ids):
        raise HTTPException(status_code=400, detail="Unknown column_def_id for this dataset")
    if len(set(payload.column_def_ids)) != len(payload.column_def_ids):
        raise HTTPException(status_code=400, detail="Duplicate column_def_ids")

    db.query(ExposedColumn).filter(ExposedColumn.dataset_id == dataset.id).delete()
    for idx, col_id in enumerate(payload.column_def_ids):
        db.add(ExposedColumn(dataset_id=dataset.id, column_def_id=col_id, display_order=idx))
    db.commit()


@api_router.get("/datasets/{dataset_id}/target-table", response_model=TargetTableOut)
def get_target_table(dataset_id: int, db: Session = Depends(get_db)):
    dataset = _get_dataset(db, dataset_id)
    setting = db.query(TargetTableSetting).filter(TargetTableSetting.dataset_id == dataset.id).first()
    return TargetTableOut(table_name=setting.table_name if setting else None)


@api_router.put("/datasets/{dataset_id}/target-table", status_code=204)
def set_target_table(dataset_id: int, payload: TargetTableIn, db: Session = Depends(get_db)):
    dataset = _get_dataset(db, dataset_id)
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


@api_router.get("/datasets/{dataset_id}/cell-rules", response_model=list[CellRuleOut])
def get_cell_rules(dataset_id: int, db: Session = Depends(get_db)):
    dataset = _get_dataset(db, dataset_id)
    rules = db.query(CellEditRule).filter(CellEditRule.dataset_id == dataset.id).all()
    return [
        CellRuleOut(row_index=r.row_index, column_def_id=r.column_def_id, options=r.options) for r in rules
    ]


@api_router.put("/datasets/{dataset_id}/cell-rules/{row_index}/{column_def_id}", status_code=204)
def set_cell_rule(
    dataset_id: int, row_index: int, column_def_id: int, payload: CellRuleIn, db: Session = Depends(get_db)
):
    dataset = _get_dataset(db, dataset_id)

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


@api_router.delete("/datasets/{dataset_id}/cell-rules/{row_index}/{column_def_id}", status_code=204)
def delete_cell_rule(dataset_id: int, row_index: int, column_def_id: int, db: Session = Depends(get_db)):
    dataset = _get_dataset(db, dataset_id)
    db.query(CellEditRule).filter(
        CellEditRule.dataset_id == dataset.id,
        CellEditRule.row_index == row_index,
        CellEditRule.column_def_id == column_def_id,
    ).delete()
    db.commit()


@api_router.put("/datasets/{dataset_id}/rows/{row_index}/assign", status_code=204)
def assign_row(dataset_id: int, row_index: int, payload: RowAssignIn, db: Session = Depends(get_db)):
    dataset = _get_dataset(db, dataset_id)
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


@api_router.put("/datasets/{dataset_id}/rows/assign-bulk", response_model=RowAssignBulkOut)
def assign_rows_bulk(dataset_id: int, payload: RowAssignBulkIn, db: Session = Depends(get_db)):
    dataset = _get_dataset(db, dataset_id)

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


@master_router.get("/admins", response_model=list[AdminUserOut])
def list_admins(db: Session = Depends(get_db)):
    admins = db.query(AdminUser).order_by(AdminUser.username).all()
    return [AdminUserOut(id=a.id, username=a.username) for a in admins]


@master_router.post("/admins", response_model=AdminUserOut, status_code=201)
def create_admin(payload: AdminUserIn, db: Session = Depends(get_db)):
    existing = db.query(AdminUser).filter(AdminUser.username == payload.username).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already exists")
    admin = AdminUser(username=payload.username, password_hash=hash_password(payload.password))
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return AdminUserOut(id=admin.id, username=admin.username)


@master_router.delete("/admins/{admin_id}", status_code=204)
def delete_admin(admin_id: int, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
    if admin is None:
        raise HTTPException(status_code=404, detail="Admin not found")
    db.delete(admin)
    db.commit()


router = APIRouter()
router.include_router(pages_router)
router.include_router(api_router)
router.include_router(master_router)

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import current_enduser_id, require_enduser, require_enduser_page
from app.db import get_db
from app.models import CellEditRule, CellEditValue, ColumnDef, Dataset, ExposedColumn, RawRow, TargetTableSetting
from app.schemas import (
    DatasetGrid,
    GridCell,
    GridColumn,
    GridResponse,
    GridRow,
    SaveEditsResponse,
    SaveRequest,
    ShipResponse,
)
from app.target import EditRequest, NotConfiguredError, ValidationError, apply_enduser_edits, ship_dataset_to_db

templates = Jinja2Templates(directory="app/templates")

pages_router = APIRouter(dependencies=[Depends(require_enduser_page)])
api_router = APIRouter(prefix="/review", dependencies=[Depends(require_enduser)])


@pages_router.get("/review")
def review_page(request: Request):
    return templates.TemplateResponse(request, "review.html", {})


def _get_dataset(db: Session, dataset_id: int) -> Dataset:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


def _build_dataset_grid(db: Session, dataset: Dataset, enduser_id: int) -> DatasetGrid | None:
    raw_rows = (
        db.query(RawRow)
        .filter(RawRow.dataset_id == dataset.id, RawRow.assigned_enduser_id == enduser_id)
        .order_by(RawRow.row_index)
        .all()
    )
    if not raw_rows:
        return None

    exposed = (
        db.query(ExposedColumn, ColumnDef)
        .join(ColumnDef, ExposedColumn.column_def_id == ColumnDef.id)
        .filter(ExposedColumn.dataset_id == dataset.id)
        .order_by(ExposedColumn.display_order)
        .all()
    )
    columns = [
        GridColumn(column_def_id=col.id, label=col.source_name, order=exp.display_order)
        for exp, col in exposed
    ]
    column_defs = {col.id: col for _, col in exposed}

    next_order = len(columns)
    admin_columns = (
        db.query(ColumnDef)
        .filter(ColumnDef.dataset_id == dataset.id, ColumnDef.is_admin_added.is_(True))
        .order_by(ColumnDef.order_index)
        .all()
    )
    for col in admin_columns:
        if col.id in column_defs:
            continue
        columns.append(GridColumn(column_def_id=col.id, label=col.source_name, order=next_order))
        column_defs[col.id] = col
        next_order += 1

    rules = db.query(CellEditRule).filter(CellEditRule.dataset_id == dataset.id).all()
    rule_map = {(r.row_index, r.column_def_id): r.options for r in rules}

    edit_values = db.query(CellEditValue).filter(CellEditValue.dataset_id == dataset.id).all()
    edit_map = {(e.row_index, e.column_def_id): e.value for e in edit_values}

    setting = db.query(TargetTableSetting).filter(TargetTableSetting.dataset_id == dataset.id).first()

    grid_rows = []
    for row in raw_rows:
        cells = []
        for col_id, col in column_defs.items():
            value = edit_map.get((row.row_index, col_id), row.data.get(col.safe_name))
            if col.is_admin_added:
                editable = True
                input_type = col.input_type
                options = col.options
            else:
                options = rule_map.get((row.row_index, col_id))
                editable = options is not None
                input_type = "dropdown" if editable else None
            cells.append(
                GridCell(
                    column_def_id=col_id,
                    value=value,
                    editable=editable,
                    input_type=input_type,
                    options=options,
                )
            )
        cells.sort(key=lambda c: next(gc.order for gc in columns if gc.column_def_id == c.column_def_id))
        grid_rows.append(GridRow(row_index=row.row_index, cells=cells))

    return DatasetGrid(
        dataset_id=dataset.id,
        label=dataset.label,
        target_table_name=setting.table_name if setting else None,
        columns=columns,
        rows=grid_rows,
    )


@api_router.get("/grid", response_model=GridResponse)
def get_grid(db: Session = Depends(get_db), enduser_id: int = Depends(current_enduser_id)):
    dataset_ids = [
        row[0]
        for row in db.query(RawRow.dataset_id)
        .filter(RawRow.assigned_enduser_id == enduser_id)
        .distinct()
        .all()
    ]
    datasets = (
        db.query(Dataset).filter(Dataset.id.in_(dataset_ids)).order_by(Dataset.created_at.desc()).all()
        if dataset_ids
        else []
    )

    grids = []
    for dataset in datasets:
        grid = _build_dataset_grid(db, dataset, enduser_id)
        if grid is not None:
            grids.append(grid)

    return GridResponse(datasets=grids)


@api_router.post("/save", response_model=SaveEditsResponse)
def save_grid(
    payload: SaveRequest,
    db: Session = Depends(get_db),
    enduser_id: int = Depends(current_enduser_id),
):
    dataset = _get_dataset(db, payload.dataset_id)
    edits = [EditRequest(row_index=e.row_index, column_def_id=e.column_def_id, value=e.value) for e in payload.edits]

    try:
        apply_enduser_edits(db, dataset, enduser_id, edits)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail={"errors": exc.errors}) from None

    return SaveEditsResponse(saved=len(edits))


@api_router.post("/datasets/{dataset_id}/ship", response_model=ShipResponse)
def ship_grid(
    dataset_id: int,
    db: Session = Depends(get_db),
    enduser_id: int = Depends(current_enduser_id),
):
    dataset = _get_dataset(db, dataset_id)

    has_rows = (
        db.query(RawRow)
        .filter(RawRow.dataset_id == dataset.id, RawRow.assigned_enduser_id == enduser_id)
        .first()
        is not None
    )
    if not has_rows:
        raise HTTPException(status_code=403, detail="You have no rows assigned in this dataset")

    try:
        result = ship_dataset_to_db(db, dataset)
    except NotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    return ShipResponse(table_name=result.table_name, row_count=result.row_count)


router = APIRouter()
router.include_router(pages_router)
router.include_router(api_router)

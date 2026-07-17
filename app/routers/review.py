from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import current_enduser_id, require_enduser, require_enduser_page
from app.db import get_db
from app.models import CellEditRule, CellEditValue, ColumnDef, Dataset, ExposedColumn, RawRow
from app.schemas import GridCell, GridColumn, GridResponse, GridRow, SaveRequest, SaveResponse
from app.target import EditRequest, NotConfiguredError, ValidationError, save_corrected_dataset

templates = Jinja2Templates(directory="app/templates")

pages_router = APIRouter(dependencies=[Depends(require_enduser_page)])
api_router = APIRouter(prefix="/review", dependencies=[Depends(require_enduser)])


@pages_router.get("/review")
def review_page(request: Request):
    return templates.TemplateResponse(request, "review.html", {})


def _get_active_dataset(db: Session) -> Dataset:
    dataset = db.query(Dataset).filter(Dataset.is_active.is_(True)).first()
    if dataset is None:
        raise HTTPException(status_code=400, detail="No dataset has been ingested yet")
    return dataset


@api_router.get("/grid", response_model=GridResponse)
def get_grid(db: Session = Depends(get_db), enduser_id: int = Depends(current_enduser_id)):
    dataset = _get_active_dataset(db)

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

    # Admin-added columns are always part of the report, regardless of the 4-6
    # exposed-column selection (which only governs ingested source columns).
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

    raw_rows = (
        db.query(RawRow)
        .filter(RawRow.dataset_id == dataset.id, RawRow.assigned_enduser_id == enduser_id)
        .order_by(RawRow.row_index)
        .all()
    )

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

    return GridResponse(columns=columns, rows=grid_rows)


@api_router.post("/save", response_model=SaveResponse)
def save_grid(
    payload: SaveRequest,
    db: Session = Depends(get_db),
    enduser_id: int = Depends(current_enduser_id),
):
    dataset = _get_active_dataset(db)
    edits = [EditRequest(row_index=e.row_index, column_def_id=e.column_def_id, value=e.value) for e in payload.edits]

    try:
        result = save_corrected_dataset(db, dataset, enduser_id, edits)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail={"errors": exc.errors}) from None
    except NotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    return SaveResponse(table_name=result.table_name, row_count=result.row_count)


router = APIRouter()
router.include_router(pages_router)
router.include_router(api_router)

from typing import Any

from pydantic import BaseModel, Field


class ColumnOut(BaseModel):
    id: int
    source_name: str
    safe_name: str
    order_index: int


class IngestDbRequest(BaseModel):
    connection_string: str
    table_name: str


class IngestResponse(BaseModel):
    dataset_id: int
    columns: list[ColumnOut]
    row_count: int


class RawRowOut(BaseModel):
    row_index: int
    values: dict[str, Any]
    assigned_enduser_id: int | None


class AdminDatasetResponse(BaseModel):
    dataset_id: int
    columns: list[ColumnOut]
    rows: list[RawRowOut]


class ExposedColumnsIn(BaseModel):
    column_def_ids: list[int] = Field(min_length=4, max_length=6)


class ExposedColumnOut(BaseModel):
    column_def_id: int
    source_name: str
    display_order: int


class TargetTableIn(BaseModel):
    table_name: str


class TargetTableOut(BaseModel):
    table_name: str | None


class CellRuleIn(BaseModel):
    options: list[str] = Field(min_length=2)


class CellRuleOut(BaseModel):
    row_index: int
    column_def_id: int
    options: list[str]


class EndUserIn(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1)


class EndUserOut(BaseModel):
    id: int
    username: str


class RowAssignIn(BaseModel):
    enduser_id: int | None = None


class RowAssignBulkIn(BaseModel):
    row_indices: list[int] = Field(min_length=1)
    enduser_id: int | None = None


class RowAssignBulkOut(BaseModel):
    updated: int


class EditIn(BaseModel):
    row_index: int
    column_def_id: int
    value: str


class SaveRequest(BaseModel):
    edits: list[EditIn] = Field(default_factory=list)


class SaveResponse(BaseModel):
    table_name: str
    row_count: int


class SaveErrorResponse(BaseModel):
    errors: list[str]


class GridCell(BaseModel):
    column_def_id: int
    value: Any
    editable: bool
    options: list[str] | None = None


class GridRow(BaseModel):
    row_index: int
    cells: list[GridCell]


class GridColumn(BaseModel):
    column_def_id: int
    label: str
    order: int


class GridResponse(BaseModel):
    columns: list[GridColumn]
    rows: list[GridRow]

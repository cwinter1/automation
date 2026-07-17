from typing import Any

from pydantic import BaseModel, Field


class ColumnOut(BaseModel):
    id: int
    source_name: str
    safe_name: str
    order_index: int
    is_admin_added: bool = False
    input_type: str | None = None
    options: list[str] | None = None


class AdminColumnIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    input_type: str  # "dropdown" | "text"
    options: list[str] | None = None


class IngestDbRequest(BaseModel):
    connection: str  # a DB_CONN_<NAME> connection name, or a raw connection string
    table_name: str
    label: str | None = None


class IngestResponse(BaseModel):
    dataset_id: int
    label: str
    columns: list[ColumnOut]
    row_count: int


class DatasetOut(BaseModel):
    id: int
    label: str
    source_type: str
    row_count: int
    column_count: int
    target_table_name: str | None = None


class RawRowOut(BaseModel):
    row_index: int
    values: dict[str, Any]
    assigned_enduser_id: int | None
    is_admin_added: bool = False


class AdminDatasetResponse(BaseModel):
    dataset_id: int
    label: str
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


class AdminUserIn(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1)


class AdminUserOut(BaseModel):
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
    dataset_id: int
    edits: list[EditIn] = Field(default_factory=list)


class SaveEditsResponse(BaseModel):
    saved: int


class ShipResponse(BaseModel):
    table_name: str
    row_count: int


class SaveErrorResponse(BaseModel):
    errors: list[str]


class GridCell(BaseModel):
    column_def_id: int
    value: Any
    editable: bool
    input_type: str | None = None  # "dropdown" | "text", meaningful only when editable
    options: list[str] | None = None


class GridRow(BaseModel):
    row_index: int
    cells: list[GridCell]


class GridColumn(BaseModel):
    column_def_id: int
    label: str
    order: int


class DatasetGrid(BaseModel):
    dataset_id: int
    label: str
    target_table_name: str | None = None
    columns: list[GridColumn]
    rows: list[GridRow]


class GridResponse(BaseModel):
    datasets: list[DatasetGrid]


class ConnectionNamesOut(BaseModel):
    names: list[str]


class MetadataColumn(BaseModel):
    source_name: str
    safe_name: str
    is_admin_added: bool


class DatasetMetadataOut(BaseModel):
    dataset_id: int
    label: str
    source_type: str
    row_count: int
    input_columns: list[MetadataColumn]
    target_table_name: str | None
    output_columns: list[MetadataColumn]

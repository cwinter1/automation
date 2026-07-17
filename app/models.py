from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EndUser(Base):
    __tablename__ = "end_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class AdminUser(Base):
    """A named admin account, created by the master admin. Distinct from the master admin
    itself, which authenticates via the shared ADMIN_PASSWORD env var and has no DB row."""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "xlsx" | "db"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    columns: Mapped[list["ColumnDef"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
    rows: Mapped[list["RawRow"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class ColumnDef(Base):
    __tablename__ = "column_defs"
    __table_args__ = (UniqueConstraint("dataset_id", "safe_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    safe_name: Mapped[str] = mapped_column(String(63), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_admin_added: Mapped[bool] = mapped_column(default=False)
    input_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "dropdown" | "text"
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)  # dropdown choices, if any

    dataset: Mapped["Dataset"] = relationship(back_populates="columns")


class RawRow(Base):
    __tablename__ = "raw_rows"
    __table_args__ = (UniqueConstraint("dataset_id", "row_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    assigned_enduser_id: Mapped[int | None] = mapped_column(
        ForeignKey("end_users.id", ondelete="SET NULL"), nullable=True
    )
    is_admin_added: Mapped[bool] = mapped_column(default=False)

    dataset: Mapped["Dataset"] = relationship(back_populates="rows")


class ExposedColumn(Base):
    __tablename__ = "exposed_columns"
    __table_args__ = (UniqueConstraint("dataset_id", "column_def_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    column_def_id: Mapped[int] = mapped_column(
        ForeignKey("column_defs.id", ondelete="CASCADE"), nullable=False
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)


class CellEditRule(Base):
    __tablename__ = "cell_edit_rules"
    __table_args__ = (UniqueConstraint("dataset_id", "row_index", "column_def_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    column_def_id: Mapped[int] = mapped_column(
        ForeignKey("column_defs.id", ondelete="CASCADE"), nullable=False
    )
    options: Mapped[list] = mapped_column(JSON, nullable=False)


class CellEditValue(Base):
    __tablename__ = "cell_edit_values"
    __table_args__ = (UniqueConstraint("dataset_id", "row_index", "column_def_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    column_def_id: Mapped[int] = mapped_column(
        ForeignKey("column_defs.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[str] = mapped_column(String, nullable=False)
    edited_by_enduser_id: Mapped[int] = mapped_column(
        ForeignKey("end_users.id"), nullable=False
    )
    edited_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class TargetTableSetting(Base):
    __tablename__ = "target_table_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    table_name: Mapped[str] = mapped_column(String(63), nullable=False)

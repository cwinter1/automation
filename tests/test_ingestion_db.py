from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert

from app.ingestion import pull_from_db


def _make_source_db(tmp_path):
    db_path = tmp_path / "source.db"
    conn_str = f"sqlite:///{db_path}"
    engine = create_engine(conn_str)
    metadata = MetaData()
    sample = Table(
        "sample",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String),
        Column("score", Integer),
    )
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(insert(sample), [{"id": 1, "name": "Alice", "score": 10}, {"id": 2, "name": "Bob", "score": 20}])
    engine.dispose()
    return conn_str


def test_pull_from_db_round_trips_rows(tmp_path):
    conn_str = _make_source_db(tmp_path)

    columns, rows = pull_from_db(conn_str, "sample")

    assert set(columns) == {"id", "name", "score"}
    assert len(rows) == 2
    names = {r["name"] for r in rows}
    assert names == {"Alice", "Bob"}


def test_pull_from_db_rejects_invalid_table_identifier(tmp_path):
    conn_str = _make_source_db(tmp_path)
    import pytest

    with pytest.raises(ValueError):
        pull_from_db(conn_str, "sample; DROP TABLE sample;--")


def test_pull_from_db_error_never_leaks_connection_string(tmp_path):
    conn_str = _make_source_db(tmp_path)
    import pytest

    with pytest.raises(ValueError) as exc_info:
        pull_from_db(conn_str, "does_not_exist")

    assert conn_str not in str(exc_info.value)

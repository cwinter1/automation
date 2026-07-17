from datetime import date

import pytest

from app.ingestion import parse_xlsx
from tests.conftest import make_xlsx_bytes


def test_parse_xlsx_round_trips_columns_and_rows():
    headers = ["Name", "Amount", "Signed Up"]
    rows = [
        ["Alice", 12.5, date(2024, 1, 1)],
        ["Bob", None, date(2024, 2, 2)],
    ]
    content = make_xlsx_bytes(headers, rows)

    columns, parsed_rows = parse_xlsx(content)

    assert columns == headers
    assert len(parsed_rows) == 2
    assert parsed_rows[0]["Name"] == "Alice"
    assert parsed_rows[0]["Amount"] == 12.5
    assert parsed_rows[0]["Signed Up"].startswith("2024-01-01")
    assert parsed_rows[1]["Amount"] is None


def test_parse_xlsx_skips_fully_blank_rows():
    headers = ["A", "B"]
    rows = [["x", "y"], [None, None], ["z", "w"]]
    content = make_xlsx_bytes(headers, rows)

    _, parsed_rows = parse_xlsx(content)

    assert len(parsed_rows) == 2
    assert parsed_rows[1]["A"] == "z"


def test_parse_xlsx_fills_blank_header_with_placeholder():
    headers = ["A", None, "C"]
    rows = [["x", "y", "z"]]
    content = make_xlsx_bytes(headers, rows)

    columns, parsed_rows = parse_xlsx(content)

    assert columns[1] == "column_2"
    assert parsed_rows[0]["column_2"] == "y"


def test_parse_xlsx_rejects_empty_sheet():
    content = make_xlsx_bytes([], [])
    with pytest.raises(ValueError):
        parse_xlsx(content)


def test_parse_xlsx_values_are_json_serializable():
    import json

    headers = ["A", "B"]
    rows = [["x", 1.5]]
    content = make_xlsx_bytes(headers, rows)
    _, parsed_rows = parse_xlsx(content)
    json.dumps(parsed_rows)  # must not raise

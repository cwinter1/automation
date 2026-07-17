import pytest

from app.ingestion import make_safe_identifier
from app.sanitize import validate_identifier


@pytest.mark.parametrize("name", ["foo", "_foo", "foo_2", "a", "A1", "col_123"])
def test_validate_identifier_accepts_good_names(name):
    assert validate_identifier(name) == name


@pytest.mark.parametrize(
    "name",
    [
        "",
        "2foo",
        "foo bar",
        "foo;DROP TABLE x--",
        'foo"bar',
        "foo`bar",
        "foo-bar",
        "a" * 100,
        None,
    ],
)
def test_validate_identifier_rejects_bad_names(name):
    with pytest.raises(ValueError):
        validate_identifier(name)


def test_make_safe_identifier_dedupes_collisions():
    existing = set()
    first = make_safe_identifier("First Name", existing)
    second = make_safe_identifier("first name", existing)
    assert first != second
    assert first == "first_name"
    assert second == "first_name_2"


def test_make_safe_identifier_falls_back_on_all_symbols():
    existing = set()
    result = make_safe_identifier("###", existing)
    assert result == "col"


def test_make_safe_identifier_prefixes_leading_digit():
    existing = set()
    result = make_safe_identifier("123abc", existing)
    assert result.startswith("_")
    assert result[0] == "_"


def test_make_safe_identifier_is_always_valid():
    existing = set()
    for raw in ["a b/c", "日本語", "SELECT * FROM x", "", "   "]:
        result = make_safe_identifier(raw, existing)
        validate_identifier(result)  # must not raise

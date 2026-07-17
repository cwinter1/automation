import re

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def validate_identifier(name: str) -> str:
    """Validate a string for safe use as a SQL identifier (table/column name).

    Raises ValueError on anything that doesn't match; never mutates the input,
    since identifiers can't be parameterized and callers must surface a clear
    400 to the admin rather than silently rewriting what they typed.
    """
    if not isinstance(name, str) or not IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid identifier: {name!r}")
    return name

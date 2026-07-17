import os

_ENV_PREFIX = "DB_CONN_"


def list_named_connections() -> dict[str, str]:
    """Named DB connections defined via DB_CONN_<NAME> environment variables.

    Keys are lowercased connection names (e.g. DB_CONN_PROD -> "prod"). Values are the
    actual connection strings, so this function's return value is only ever used server-side
    (never sent to a client) — see get_connection_names for the client-safe listing.
    """
    return {
        key[len(_ENV_PREFIX):].lower(): value
        for key, value in os.environ.items()
        if key.startswith(_ENV_PREFIX) and value
    }


def get_connection_names() -> list[str]:
    """Names only, safe to expose to the admin UI (never the underlying connection strings)."""
    return sorted(list_named_connections().keys())


def resolve_connection(name_or_string: str) -> str:
    """Resolve a named connection (DB_CONN_<NAME>) to its connection string, or pass through
    a raw connection string unchanged if it doesn't match a configured name."""
    named = list_named_connections()
    return named.get(name_or_string, name_or_string)

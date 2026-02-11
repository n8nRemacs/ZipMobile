"""
Lightweight Supabase PostgREST wrapper.
Copied from avito-xapi with the same interface for consistency.
"""
import httpx
from dataclasses import dataclass
from typing import Any
from src.config import settings


@dataclass
class QueryResult:
    data: list[dict[str, Any]]
    count: int | None = None


class QueryBuilder:
    """Chainable PostgREST query builder mimicking supabase-py API."""

    def __init__(self, client: httpx.Client, table: str, base_url: str, headers: dict):
        self._client = client
        self._table = table
        self._base_url = f"{base_url}/rest/v1/{table}"
        self._headers = headers
        self._params: dict[str, str] = {}
        self._method = "GET"
        self._body: Any = None
        self._select_columns = "*"

    def select(self, columns: str = "*") -> "QueryBuilder":
        self._method = "GET"
        self._select_columns = columns
        self._params["select"] = columns
        return self

    def insert(self, data: dict | list) -> "QueryBuilder":
        self._method = "POST"
        self._body = data
        self._headers["Prefer"] = "return=representation"
        return self

    def update(self, data: dict) -> "QueryBuilder":
        self._method = "PATCH"
        self._body = data
        self._headers["Prefer"] = "return=representation"
        return self

    def delete(self) -> "QueryBuilder":
        self._method = "DELETE"
        self._headers["Prefer"] = "return=representation"
        return self

    def eq(self, column: str, value: Any) -> "QueryBuilder":
        self._params[column] = f"eq.{value}"
        return self

    def neq(self, column: str, value: Any) -> "QueryBuilder":
        self._params[column] = f"neq.{value}"
        return self

    def gt(self, column: str, value: Any) -> "QueryBuilder":
        self._params[column] = f"gt.{value}"
        return self

    def gte(self, column: str, value: Any) -> "QueryBuilder":
        self._params[column] = f"gte.{value}"
        return self

    def lt(self, column: str, value: Any) -> "QueryBuilder":
        self._params[column] = f"lt.{value}"
        return self

    def lte(self, column: str, value: Any) -> "QueryBuilder":
        self._params[column] = f"lte.{value}"
        return self

    def order(self, column: str, *, desc: bool = False) -> "QueryBuilder":
        direction = "desc" if desc else "asc"
        self._params["order"] = f"{column}.{direction}"
        return self

    def limit(self, count: int) -> "QueryBuilder":
        self._params["limit"] = str(count)
        return self

    def execute(self) -> QueryResult:
        if self._method == "GET":
            resp = self._client.get(self._base_url, params=self._params, headers=self._headers)
        elif self._method == "POST":
            resp = self._client.post(self._base_url, json=self._body, params=self._params, headers=self._headers)
        elif self._method == "PATCH":
            resp = self._client.patch(self._base_url, json=self._body, params=self._params, headers=self._headers)
        elif self._method == "DELETE":
            resp = self._client.delete(self._base_url, params=self._params, headers=self._headers)
        else:
            raise ValueError(f"Unknown method: {self._method}")

        resp.raise_for_status()

        try:
            data = resp.json()
        except Exception:
            data = []

        if isinstance(data, dict):
            data = [data]

        return QueryResult(data=data if isinstance(data, list) else [])


class SupabaseClient:
    """Minimal Supabase client using PostgREST."""

    def __init__(self, url: str, key: str):
        self._url = url.rstrip("/")
        self._key = key
        self._client = httpx.Client(timeout=30.0)

    def _headers(self) -> dict:
        return {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }

    def table(self, name: str) -> QueryBuilder:
        return QueryBuilder(self._client, name, self._url, self._headers())


_client: SupabaseClient | None = None


def get_supabase() -> SupabaseClient:
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_key)
    return _client


def create_client(url: str, key: str) -> SupabaseClient:
    return SupabaseClient(url, key)

"""Read-only SQL access for the Data Analyst agent.

Defence in depth - a query must pass ALL of these layers:
  1. this validator (single SELECT/WITH statement, no write/DDL keywords, no comments)
  2. a READ ONLY transaction with a statement timeout
  3. a dedicated database role (`analyst_ro`) that only has SELECT on the demo schema
"""
from __future__ import annotations

import re

from app.tools.base import ToolError

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|call|do|merge|vacuum|"
    r"pg_sleep|set|reset|execute|lock|listen|notify|into)\b",
    re.IGNORECASE,
)
_LITERAL = re.compile(r"'(?:[^']|'')*'")


def validate_readonly_sql(sql: str) -> str:
    query = sql.strip().rstrip(";").strip()
    if not query:
        raise ToolError("empty query")
    if not re.match(r"(?is)^(select|with)\b", query):
        raise ToolError("only SELECT queries are allowed")
    scrubbed = _LITERAL.sub("''", query)  # ignore ; and keywords that appear inside string literals
    if ";" in scrubbed:
        raise ToolError("only a single statement is allowed")
    if "--" in scrubbed or "/*" in scrubbed:
        raise ToolError("SQL comments are not allowed")
    match = _FORBIDDEN.search(scrubbed)
    if match:
        raise ToolError(f"keyword not allowed in read-only queries: {match.group(1).upper()}")
    return query


def format_rows(columns: list[str], rows: list, truncated: bool) -> str:
    if not rows:
        return "(0 rows)"
    lines = [" | ".join(columns), " | ".join("---" for _ in columns)]
    lines += [" | ".join("" if v is None else str(v) for v in row) for row in rows]
    if truncated:
        lines.append("...(more rows exist; add a LIMIT or aggregate)")
    return "\n".join(lines)


def make_sql_tool(engine, max_rows: int = 50, timeout_ms: int = 5000):
    from sqlalchemy import text

    def run(args: dict) -> str:
        query = validate_readonly_sql(str(args.get("sql", "")))
        with engine.connect() as conn:
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            conn.exec_driver_sql(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
            result = conn.execute(text(query))
            rows = result.fetchmany(max_rows + 1)
            columns = list(result.keys())
            conn.rollback()
        return format_rows(columns, rows[:max_rows], len(rows) > max_rows)

    return run


def make_schema_tool(engine, schema: str = "demo"):
    from sqlalchemy import text

    def run(_args: dict) -> str:
        sql = text(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = :schema ORDER BY table_name, ordinal_position"
        )
        with engine.connect() as conn:
            rows = conn.execute(sql, {"schema": schema}).fetchall()
        if not rows:
            return "(no tables visible)"
        tables: dict[str, list[str]] = {}
        for table, column, dtype in rows:
            tables.setdefault(table, []).append(f"{column} {dtype}")
        return "\n".join(f"{table}({', '.join(cols)})" for table, cols in tables.items())

    return run

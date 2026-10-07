from app.tools.base import ToolError
from app.tools.sql import format_rows, validate_readonly_sql


def rejected(sql: str) -> bool:
    try:
        validate_readonly_sql(sql)
    except ToolError:
        return True
    return False


def test_plain_selects_pass():
    assert validate_readonly_sql("SELECT * FROM product_metrics;") == "SELECT * FROM product_metrics"
    assert validate_readonly_sql("with t as (select 1) select * from t")


def test_created_at_style_columns_are_not_mistaken_for_keywords():
    assert validate_readonly_sql("SELECT created_at, updated_at, offset_days FROM t")


def test_keywords_inside_string_literals_are_ignored():
    assert validate_readonly_sql("SELECT * FROM t WHERE note = 'please delete; drop it'") is not None


def test_writes_and_ddl_are_blocked():
    for sql in [
        "DELETE FROM product_metrics",
        "UPDATE product_metrics SET revenue_usd = 0",
        "INSERT INTO product_metrics VALUES (1)",
        "DROP TABLE product_metrics",
        "SELECT * INTO backup FROM product_metrics",
        "WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x",
        "COPY product_metrics TO '/tmp/x'",
    ]:
        assert rejected(sql), sql


def test_stacked_statements_comments_and_sleep_are_blocked():
    for sql in [
        "SELECT 1; DROP TABLE runs",
        "SELECT 1 -- hidden",
        "SELECT /* x */ 1",
        "SELECT pg_sleep(100)",
        "SET ROLE postgres",
        "",
        "   ;  ",
    ]:
        assert rejected(sql), sql


def test_format_rows():
    text = format_rows(["a", "b"], [(1, None), (2, "x")], truncated=True)
    assert text.splitlines()[0] == "a | b"
    assert "1 | " in text and "more rows exist" in text
    assert format_rows(["a"], [], False) == "(0 rows)"

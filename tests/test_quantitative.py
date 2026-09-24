"""Unit and integration tests for the quantitative NL-to-SQL agent."""

import sqlite3

import pytest

from agents.quantitative import (
    NotSQLError,
    QuantitativeAgent,
    UnsafeSQLError,
    _extract_sql,
    _validate_sql,
)


class TestExtractSQL:
    def test_plain_sql_passes_through(self):
        assert _extract_sql("SELECT * FROM sales") == "SELECT * FROM sales"

    def test_strips_markdown_fence_with_sql_tag(self):
        assert _extract_sql("```sql\nSELECT * FROM sales;\n```") == "SELECT * FROM sales"

    def test_strips_markdown_fence_without_sql_tag(self):
        assert _extract_sql("```\nSELECT 1;\n```") == "SELECT 1"

    def test_strips_surrounding_whitespace_and_trailing_semicolon(self):
        assert _extract_sql("  SELECT 1;  ") == "SELECT 1"


class TestValidateSQL:
    def test_valid_select_raises_nothing(self):
        _validate_sql("SELECT region, revenue FROM sales")

    def test_prose_refusal_raises_not_sql_error(self):
        with pytest.raises(NotSQLError):
            _validate_sql("I don't have enough information to answer this question.")

    @pytest.mark.parametrize(
        "bad_sql",
        [
            "DROP TABLE sales",
            "DELETE FROM sales",
            "UPDATE sales SET revenue = 0",
            "INSERT INTO sales VALUES (1,2,3,4)",
            "PRAGMA table_info(sales)",
            "ALTER TABLE sales ADD COLUMN x TEXT",
            "CREATE TABLE evil (id INTEGER)",
        ],
    )
    def test_forbidden_keywords_raise_unsafe_sql_error(self, bad_sql):
        with pytest.raises(UnsafeSQLError):
            _validate_sql(bad_sql)

    def test_multiple_statements_raise_unsafe_sql_error(self):
        with pytest.raises(UnsafeSQLError):
            _validate_sql("SELECT * FROM sales; DROP TABLE sales")

    def test_forbidden_keyword_takes_priority_over_missing_select_prefix(self):
        with pytest.raises(UnsafeSQLError):
            _validate_sql("DROP TABLE sales")


class TestQuantitativeAgentQuery:
    def test_real_query_against_seeded_db(self, fake_claude_factory, temp_db):
        claude = fake_claude_factory(
            "SELECT region, ROUND(SUM(revenue),2) as total FROM sales GROUP BY region"
        )
        agent = QuantitativeAgent(claude_client=claude, db_path=temp_db)

        result = agent.query("total revenue by region")

        assert result["columns"] == ["region", "total"]
        assert len(result["rows"]) == 4
        assert result["detail"]["row_count"] == 4
        assert "execution_time_ms" in result["detail"]

    def test_prose_refusal_surfaces_directly_without_running_sql(self, fake_claude_factory, temp_db):
        refusal = "I don't have enough information to answer this question."
        claude = fake_claude_factory(refusal)
        agent = QuantitativeAgent(claude_client=claude, db_path=temp_db)

        result = agent.query("something unanswerable")

        assert result["answer"] == refusal
        assert result["sql"] is None
        assert result["rows"] == []
        assert result["detail"]["reason"] == "not_answerable_from_schema"

    def test_unsafe_sql_is_rejected_before_execution(self, fake_claude_factory, temp_db):
        claude = fake_claude_factory("DROP TABLE sales")
        agent = QuantitativeAgent(claude_client=claude, db_path=temp_db)

        result = agent.query("delete everything")

        assert "safety checks" in result["answer"].lower()
        assert result["rows"] == []

        conn = sqlite3.connect(temp_db)
        count = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        conn.close()
        assert count == 24

    def test_invalid_column_name_reports_execution_error_gracefully(self, fake_claude_factory, temp_db):
        claude = fake_claude_factory("SELECT nonexistent_column FROM sales")
        agent = QuantitativeAgent(claude_client=claude, db_path=temp_db)

        result = agent.query("bad column question")

        assert "failed to execute" in result["answer"].lower()
        assert result["rows"] == []

    def test_readonly_connection_blocks_writes_even_if_validation_were_bypassed(self, temp_db):
        conn = sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True)
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM sales")
        conn.close()

    def test_query_with_no_matching_rows_reports_no_results(self, fake_claude_factory, temp_db):
        claude = fake_claude_factory("SELECT * FROM sales WHERE region = 'Antarctica'")
        agent = QuantitativeAgent(claude_client=claude, db_path=temp_db)

        result = agent.query("sales in a region that doesn't exist")

        assert result["rows"] == []
        assert result["answer"] == "The query returned no results."

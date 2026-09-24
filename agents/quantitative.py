"""Quantitative NL-to-SQL agent: turns a natural language question into a
read-only SQL query against the SQLite database, executes it, and returns
tabular results.
"""

import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from anthropic import Anthropic

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "enterprise.db"
MODEL = "claude-haiku-4-5"

# Generated SQL is rejected if it contains any of these, case-insensitively,
# as a whole word -- this is a defense-in-depth check, not the only one.
# The primary guarantee is that we only ever execute a single SELECT statement.
_FORBIDDEN_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter", "create",
    "replace", "attach", "detach", "pragma", "vacuum", "reindex",
}

SCHEMA_DESCRIPTION = """
Tables:

sales(id INTEGER, region TEXT, quarter TEXT, revenue REAL, units_sold INTEGER)
  - region is one of: 'North America', 'EMEA', 'APAC', 'LATAM'
  - quarter is like '2024-Q1', '2024-Q2', ... '2025-Q2'

customers(id INTEGER, signup_quarter TEXT, region TEXT, churned INTEGER)
  - churned is 1 if the customer has churned, 0 otherwise
  - signup_quarter and region use the same values as in sales
"""

SYSTEM_PROMPT = f"""You translate natural language questions into a single
SQLite SELECT statement against this schema:
{SCHEMA_DESCRIPTION}

Rules:
- Output ONLY the SQL statement, no explanation, no markdown code fences.
- Only ever write a SELECT statement. Never write INSERT, UPDATE, DELETE,
  DROP, ALTER, CREATE, or any other statement that modifies the database.
- Only write a single statement. Do not chain multiple statements with ';'.
- Use standard SQLite syntax (e.g. ROUND(), strftime() are available)."""


class UnsafeSQLError(Exception):
    """Raised when generated SQL is actively unsafe (multiple statements or
    a forbidden write/DDL keyword) -- as opposed to simply not being SQL.
    """


class NotSQLError(Exception):
    """Raised when the model didn't produce a SELECT statement at all, e.g.
    because it correctly explained in prose that the question isn't
    answerable from this schema. Not a security concern -- just no query.
    """


def _extract_sql(raw_text: str) -> str:
    """Strips markdown code fences if the model added them despite instructions."""
    text = raw_text.strip()
    fence_match = re.match(r"^```(?:sql)?\s*(.*?)\s*```$", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()
    return text.rstrip(";").strip()


def _validate_sql(sql: str) -> None:
    """Three checks, in order of security relevance:
    1. Multiple statements -- always unsafe, regardless of prefix.
    2. Forbidden write/DDL keyword -- always unsafe, regardless of prefix.
       (Checked before the SELECT-prefix check so "DROP TABLE ..." is
       correctly flagged as unsafe, not mistaken for a prose refusal.)
    3. Doesn't start with SELECT -- likely the model correctly explained in
       prose why it can't answer. Not a security concern, just no query.
    """
    if ";" in sql:
        raise UnsafeSQLError("Generated SQL contains multiple statements (';').")

    tokens = set(re.findall(r"[a-zA-Z_]+", sql.lower()))
    forbidden_found = tokens & _FORBIDDEN_KEYWORDS
    if forbidden_found:
        raise UnsafeSQLError(f"Generated SQL contains forbidden keyword(s): {forbidden_found}")

    if not re.match(r"^\s*select\b", sql, re.IGNORECASE):
        raise NotSQLError(f"Model did not return a SELECT statement: {sql!r}")


class QuantitativeAgent:
    def __init__(self, claude_client: Anthropic, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.claude = claude_client
        self.db_path = Path(db_path)

    def _generate_sql(self, question: str) -> str:
        response = self.claude.messages.create(
            model=MODEL,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": question}],
        )
        raw_text = "".join(block.text for block in response.content if block.type == "text")
        return _extract_sql(raw_text)

    def query(self, question: str) -> dict[str, Any]:
        sql = self._generate_sql(question)
        logger.info("Generated SQL for question %r: %s", question, sql)

        try:
            _validate_sql(sql)
        except NotSQLError:
            logger.info("Model did not produce SQL for question %r: %s", question, sql)
            return {
                "answer": sql,  # the model's own prose explanation of why it can't answer
                "columns": [],
                "rows": [],
                "sql": None,
                "detail": {"reason": "not_answerable_from_schema"},
            }
        except UnsafeSQLError as e:
            logger.error("Rejected unsafe SQL: %s", e)
            return {
                "answer": "I generated a query that didn't pass safety checks, so I didn't run it.",
                "columns": [],
                "rows": [],
                "sql": sql,
                "detail": {"error": str(e)},
            }

        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        try:
            cursor = conn.cursor()
            start = time.perf_counter()
            try:
                cursor.execute(sql)
                rows = cursor.fetchall()
                columns = [d[0] for d in cursor.description] if cursor.description else []
            except sqlite3.Error as e:
                elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
                logger.error("SQL execution failed: %s (sql=%r)", e, sql)
                return {
                    "answer": f"The generated query failed to execute: {e}",
                    "columns": [],
                    "rows": [],
                    "sql": sql,
                    "detail": {"error": str(e), "execution_time_ms": elapsed_ms},
                }
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        finally:
            conn.close()

        logger.info("Query executed in %.2fms, %d rows returned", elapsed_ms, len(rows))
        return {
            "answer": self._format_answer(columns, rows),
            "columns": columns,
            "rows": rows,
            "sql": sql,
            "detail": {"execution_time_ms": elapsed_ms, "row_count": len(rows)},
        }

    @staticmethod
    def _format_answer(columns: list[str], rows: list[tuple]) -> str:
        if not rows:
            return "The query returned no results."
        header = " | ".join(columns)
        body = "\n".join(" | ".join(str(v) for v in row) for row in rows[:20])
        suffix = f"\n... ({len(rows) - 20} more rows)" if len(rows) > 20 else ""
        return f"{header}\n{body}{suffix}"

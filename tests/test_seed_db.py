"""Tests for data/seed_db.py's main() entry point."""

import sqlite3

import data.seed_db as seed_db


def test_main_creates_and_seeds_the_database(tmp_path, monkeypatch):
    db_path = tmp_path / "main_test.db"
    monkeypatch.setattr(seed_db, "DB_PATH", db_path)

    seed_db.main()

    assert db_path.exists()
    conn = sqlite3.connect(db_path)
    try:
        sales_count = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        customers_count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    finally:
        conn.close()

    assert sales_count == 24
    assert customers_count == 500


def test_main_is_reproducible_across_runs(tmp_path, monkeypatch):
    db_path = tmp_path / "repro_test.db"
    monkeypatch.setattr(seed_db, "DB_PATH", db_path)

    seed_db.main()
    conn = sqlite3.connect(db_path)
    first_run_revenue = conn.execute("SELECT SUM(revenue) FROM sales").fetchone()[0]
    conn.close()

    seed_db.main()
    conn = sqlite3.connect(db_path)
    second_run_revenue = conn.execute("SELECT SUM(revenue) FROM sales").fetchone()[0]
    row_count = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    conn.close()

    assert first_run_revenue == second_run_revenue
    assert row_count == 24

"""Creates and seeds data/enterprise.db with synthetic sales and customer data.

Run this once before using the quantitative agent:
    uv run python data/seed_db.py
"""

import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "enterprise.db"

REGIONS = ["North America", "EMEA", "APAC", "LATAM"]
QUARTERS = ["2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4", "2025-Q1", "2025-Q2"]


def build_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS sales;
        DROP TABLE IF EXISTS customers;

        CREATE TABLE sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region TEXT NOT NULL,
            quarter TEXT NOT NULL,
            revenue REAL NOT NULL,
            units_sold INTEGER NOT NULL
        );

        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signup_quarter TEXT NOT NULL,
            region TEXT NOT NULL,
            churned INTEGER NOT NULL DEFAULT 0
        );
        """
    )


def seed_sales(conn: sqlite3.Connection, rng: random.Random) -> None:
    rows = []
    for region in REGIONS:
        base = rng.uniform(80_000, 250_000)
        for i, quarter in enumerate(QUARTERS):
            trend = base * (1 + 0.04 * i)
            revenue = round(trend * rng.uniform(0.9, 1.1), 2)
            units = int(revenue / rng.uniform(40, 90))
            rows.append((region, quarter, revenue, units))
    conn.executemany(
        "INSERT INTO sales (region, quarter, revenue, units_sold) VALUES (?, ?, ?, ?)",
        rows,
    )


def seed_customers(conn: sqlite3.Connection, rng: random.Random, n: int = 500) -> None:
    rows = []
    for _ in range(n):
        region = rng.choice(REGIONS)
        signup_quarter = rng.choice(QUARTERS)
        churned = 1 if rng.random() < 0.18 else 0
        rows.append((signup_quarter, region, churned))
    conn.executemany(
        "INSERT INTO customers (signup_quarter, region, churned) VALUES (?, ?, ?)",
        rows,
    )


def main() -> None:
    rng = random.Random(42)
    conn = sqlite3.connect(DB_PATH)
    try:
        build_schema(conn)
        seed_sales(conn, rng)
        seed_customers(conn, rng)
        conn.commit()
    finally:
        conn.close()
    print(f"Seeded {DB_PATH} with sales and customers tables.")


if __name__ == "__main__":
    main()

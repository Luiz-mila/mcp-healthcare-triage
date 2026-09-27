"""
Load Synthea's raw CSV output into a local DuckDB database.

Run this whenever new synthetic data is generated (Step 2) and needs to be
made available for the MCP server (Step 4) to query.

Usage:
    python src/load_data.py
"""

import os
from pathlib import Path

import duckdb
from dotenv import load_dotenv

load_dotenv()

# Where Synthea wrote the raw CSVs (Step 2). Relative path: works whether this
# script runs directly in the venv (cwd = project root) or inside the "etl"
# Docker service (cwd = /app, with ./data mounted at /app/data).
RAW_DIR = Path(os.getenv("SYNTHEA_RAW_DIR", "data/raw/csv"))

# Where the DuckDB file will live.
DB_PATH = Path(os.getenv("DUCKDB_PATH", "data/processed/healthcare.duckdb"))

# Only the Synthea tables our three MCP tools actually need — keep it lean.
TABLES = ["patients", "conditions", "medications", "allergies", "encounters", "procedures"]


def load_table(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    csv_path = RAW_DIR / f"{table_name}.csv"
    if not csv_path.exists():
        # Synthea only writes a CSV for tables that have at least one row.
        # With a small population, a rare table (e.g. allergies) may simply
        # have no data this run — that's expected, not a bug, so we warn
        # and move on instead of crashing the whole load.
        print(f"WARNING: {csv_path} not found — skipping '{table_name}' "
              "(no rows generated this run?)")
        return False

    con.execute(
        f"""
        CREATE OR REPLACE TABLE {table_name} AS
        SELECT * FROM read_csv_auto(?, header = true)
        """,
        [str(csv_path)],
    )
    count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    print(f"Loaded {count:,} rows into '{table_name}'")
    return True


def seed_drug_interactions(con: duckdb.DuckDBPyConnection) -> None:
    """
    Synthea generates patient data, not clinical reference knowledge — a
    drug-interaction table isn't something it exports. We seed a small,
    curated table ourselves so `check_drug_interaction` (Step 4) has
    something real to query. This is a toy dataset for the portfolio
    project, not a clinical source of truth (see README disclaimer).
    """
    con.execute("DROP TABLE IF EXISTS drug_interactions")
    con.execute(
        """
        CREATE TABLE drug_interactions (
            drug_a VARCHAR,
            drug_b VARCHAR,
            severity VARCHAR,
            description VARCHAR
        )
        """
    )
    con.executemany(
        "INSERT INTO drug_interactions VALUES (?, ?, ?, ?)",
        [
            ("Warfarin", "Aspirin", "major",
             "Increased risk of bleeding when combined."),
            ("Warfarin", "Ibuprofen", "major",
             "NSAIDs increase bleeding risk in patients on anticoagulants."),
            ("Simvastatin", "Clarithromycin", "major",
             "Increased risk of myopathy and rhabdomyolysis."),
            ("Lisinopril", "Spironolactone", "moderate",
             "Combined use raises the risk of hyperkalemia."),
            ("Metformin", "Contrast media", "moderate",
             "Risk of lactic acidosis after iodinated contrast imaging."),
        ],
    )
    print("Seeded 'drug_interactions' with 5 reference rows")


def main() -> None:
    if not RAW_DIR.exists():
        raise FileNotFoundError(
            f"{RAW_DIR} does not exist. Run Step 2 first: "
            "docker compose run --rm synthea"
        )

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    try:
        for table in TABLES:
            load_table(con, table)
        seed_drug_interactions(con)
    finally:
        con.close()
    print(f"\nDone. Database ready at: {DB_PATH}")


if __name__ == "__main__":
    main()
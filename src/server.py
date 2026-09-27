"""
MCP server exposing three tools that let Claude query the synthetic
healthcare database built in Steps 2-3: patient history, current
medications, and drug-interaction checks.

Run manually (for local testing over stdio):
    python src/server.py
"""

import os
from pathlib import Path

import duckdb
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

DB_PATH = Path(os.getenv("DUCKDB_PATH", "data/processed/healthcare.duckdb"))

mcp = FastMCP("healthcare-triage")


def _connect() -> duckdb.DuckDBPyConnection:
    # read_only=True: this server only ever queries, never writes. That
    # also lets load_data.py refresh the data without fighting over a
    # file lock, and protects against a bug here accidentally mutating
    # patient data.
    return duckdb.connect(str(DB_PATH), read_only=True)


@mcp.tool()
def get_patient_history(patient_id: str) -> dict:
    """
    Look up a patient's clinical history: past diagnoses, recorded
    allergies, and past procedures.

    Args:
        patient_id: the Synthea patient UUID (the 'Id' column in the
            'patients' table).
    """
    con = _connect()
    try:
        conditions = con.execute(
            "SELECT DESCRIPTION, CAST(START AS VARCHAR), CAST(STOP AS VARCHAR) "
            "FROM conditions WHERE PATIENT = ? ORDER BY START DESC",
            [patient_id],
        ).fetchall()

        allergies = con.execute(
            "SELECT DESCRIPTION, REACTION1, SEVERITY1 FROM allergies "
            "WHERE PATIENT = ?",
            [patient_id],
        ).fetchall()

        procedures = con.execute(
            "SELECT DESCRIPTION, CAST(START AS VARCHAR) "
            "FROM procedures WHERE PATIENT = ? ORDER BY START DESC LIMIT 20",
            [patient_id],
        ).fetchall()

        if not conditions and not allergies and not procedures:
            return {"error": f"No records found for patient_id '{patient_id}'."}

        return {
            "patient_id": patient_id,
            "conditions": [
                {"description": d, "start": s, "stop": e}
                for d, s, e in conditions
            ],
            "allergies": [
                {"description": d, "reaction": r, "severity": sv}
                for d, r, sv in allergies
            ],
            "past_procedures": [
                {"description": d, "date": s} for d, s in procedures
            ],
        }
    finally:
        con.close()


@mcp.tool()
def get_current_medications(patient_id: str) -> dict:
    """
    List the medications a patient is currently taking (no STOP date
    recorded, i.e. still active as of the last encounter in the data).

    Args:
        patient_id: the Synthea patient UUID.
    """
    con = _connect()
    try:
        rows = con.execute(
            "SELECT DESCRIPTION, CAST(START AS VARCHAR) "
            "FROM medications WHERE PATIENT = ? AND STOP IS NULL "
            "ORDER BY START DESC",
            [patient_id],
        ).fetchall()
        return {
            "patient_id": patient_id,
            "current_medications": [
                {"description": d, "start": s} for d, s in rows
            ],
        }
    finally:
        con.close()


@mcp.tool()
def check_drug_interaction(medication_a: str, medication_b: str) -> dict:
    """
    Check whether two medications have a known interaction, using the
    curated reference table seeded in Step 3. Matching is a
    case-insensitive substring match (so "Warfarin Sodium 5 MG Oral
    Tablet" matches the reference drug "Warfarin"), and checks both
    orderings of the pair.

    Args:
        medication_a: name of the first medication (e.g. "Warfarin").
        medication_b: name of the second medication (e.g. "Aspirin").
    """
    con = _connect()
    try:
        row = con.execute(
            """
            SELECT severity, description FROM drug_interactions
            WHERE (? ILIKE '%' || drug_a || '%' AND ? ILIKE '%' || drug_b || '%')
               OR (? ILIKE '%' || drug_b || '%' AND ? ILIKE '%' || drug_a || '%')
            """,
            [medication_a, medication_b, medication_a, medication_b],
        ).fetchone()

        if row is None:
            return {
                "interaction_found": False,
                "note": (
                    "No known interaction in this project's reference table "
                    "(a small, curated demo dataset — not a clinical source "
                    "of truth)."
                ),
            }

        severity, description = row
        return {
            "interaction_found": True,
            "severity": severity,
            "description": description,
        }
    finally:
        con.close()


if __name__ == "__main__":
    mcp.run(transport="stdio")
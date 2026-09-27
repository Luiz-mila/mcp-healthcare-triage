"""
Integration tests for the three MCP tools in src/server.py.

These run against the real DuckDB database built in Steps 2-3 (not a
mock) — they double as a sanity check that the whole pipeline (Synthea
-> DuckDB -> server) still works end to end after any change.

Usage:
    pytest
"""

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import server  # noqa: E402


@pytest.fixture(scope="module")
def a_patient_id():
    """
    Grab a real patient id straight from the database, instead of a
    hardcoded UUID — keeps the test valid even if you regenerate the
    Synthea data with a different population.
    """
    con = duckdb.connect(str(server.DB_PATH), read_only=True)
    try:
        row = con.execute("SELECT Id FROM patients LIMIT 1").fetchone()
    finally:
        con.close()
    assert row is not None, "No patients found — did you run Steps 2 and 3?"
    return row[0]


def test_get_patient_history_returns_expected_shape(a_patient_id):
    result = server.get_patient_history(a_patient_id)
    assert result["patient_id"] == a_patient_id
    assert "conditions" in result
    assert "allergies" in result
    assert "past_procedures" in result


def test_get_patient_history_unknown_patient_returns_error():
    result = server.get_patient_history("not-a-real-patient-id")
    assert "error" in result


def test_get_current_medications_returns_a_list(a_patient_id):
    result = server.get_current_medications(a_patient_id)
    assert result["patient_id"] == a_patient_id
    assert isinstance(result["current_medications"], list)


def test_check_drug_interaction_known_pair_is_found():
    result = server.check_drug_interaction("Warfarin", "Aspirin")
    assert result["interaction_found"] is True
    assert result["severity"] == "major"


def test_check_drug_interaction_matches_partial_drug_names():
    # Real Synthea data records e.g. "Warfarin Sodium 5 MG Oral Tablet",
    # not just "Warfarin" — this is what the ILIKE substring match in
    # server.py is actually for.
    result = server.check_drug_interaction(
        "Warfarin Sodium 5 MG Oral Tablet", "aspirin 81 MG Oral Tablet"
    )
    assert result["interaction_found"] is True


def test_check_drug_interaction_reversed_order_still_matches():
    result = server.check_drug_interaction("Aspirin", "Warfarin")
    assert result["interaction_found"] is True


def test_check_drug_interaction_no_known_pair_returns_false():
    result = server.check_drug_interaction("Paracetamol", "Vitamin C")
    assert result["interaction_found"] is False
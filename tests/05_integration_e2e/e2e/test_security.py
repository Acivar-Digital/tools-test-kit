import os

import pytest

from src.bot.db import Database


def test_case_5_1_sql_injection_prevention():
    """Test Case 5.1: SQL injection prevention via parameterization"""
    db = Database("test_security.db")
    try:
        # Create table
        db._execute_query("CREATE TABLE IF NOT EXISTS test_users (id INTEGER PRIMARY KEY, name TEXT)")

        # Malicious input
        malicious_id = 999
        malicious_name = "Jia Zi'); DROP TABLE test_users; --"

        # Insert using the standard method (parameterized)
        db._execute_query("INSERT OR REPLACE INTO test_users (id, name) VALUES (?, ?)", (malicious_id, malicious_name))

        # Check if table still exists
        res = db._execute_query("SELECT name FROM test_users WHERE id = ?", (malicious_id,), fetch_all=True)
        assert len(res) == 1
        assert res[0]["name"] == malicious_name

        # Check that the table WAS NOT dropped
        res_all = db._execute_query("SELECT COUNT(*) as count FROM test_users", fetch_all=True)
        assert res_all[0]["count"] >= 1
    finally:
        db.close()
        if os.path.exists("test_security.db"):
            try:
                os.remove("test_security.db")
            except PermissionError:
                pass  # Still locked on some Windows envs, but we tried


def test_case_5_2_data_privacy_placeholder():
    """Test Case 5.2: Data privacy (PII masking) - Placeholder for missing implementation"""
    # Since mask_pii doesn't exist yet, we document this as a finding
    pytest.skip("mask_pii function not implemented in codebase")

"""test_read_memory_bridge.py — REMOVED.

The SYSTEM NOTE nudge was moved from GuardToolset.call_tool (removed per
Item 3) to the function-level wrappers in tools.py (read_file,
batch_read, and all 8 search tools prepend _REMEMBER_NUDGE). GuardToolset
no longer injects any remember/remember_fact nudge. These tests were
testing the old GuardToolset injection that no longer exists.
"""

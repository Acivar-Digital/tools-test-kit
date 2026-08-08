import pytest
from unittest.mock import patch, MagicMock
from src2.interfaces.telegram.chronomancer.state_writer import _last_exchange, update_user_state_background
from src2.core.memory.memory_manager import memory_manager, _db

@pytest.mark.asyncio
async def test_last_exchange_memory_leak_fix():
    user_id = 999123
    current_exchange = "Test exchange"
    
    # Pre-populate the dict to simulate an active debounce state
    _last_exchange[user_id] = current_exchange
    
    # We expect the StateWriter to pop the user_id out in the finally block
    # We will mock the agent run to return immediately and avoid LLM call
    with patch("src2.interfaces.telegram.chronomancer.state_writer.state_writer_agent.run") as mock_run:
        mock_run.return_value = MagicMock(output=MagicMock(model_dump_json=lambda: "{}"))
        
        # We also mock Redis and Mem0 to prevent external connections
        with patch("redis.asyncio.from_url"), \
             patch("src2.interfaces.telegram.chronomancer.state_writer._read_mem0", return_value=""):
             
            await update_user_state_background(user_id, current_exchange, "GeJu", [])
            
    # CRITICAL: The user's entry should be removed from the dict (no memory leak)
    assert user_id not in _last_exchange


def test_database_per_call_fix():
    # Verify that memory_manager has a module-level _db instance
    assert _db is not None
    assert _db.conn is not None
    
    # Verify _resolve_id uses the singleton instead of creating a new one
    with patch.object(_db, 'get_semantic_id', return_value="SGUSD123") as mock_get:
        result = memory_manager._resolve_id(123)
        assert result == "SGUSD123"
        mock_get.assert_called_once_with(123, "telegram")

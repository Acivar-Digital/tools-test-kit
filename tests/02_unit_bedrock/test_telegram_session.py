import pytest

from src2.interfaces.telegram.session import ChatMessage, Session, SessionMetadata


def test_session_metadata_fields():
    """Test that SessionMetadata accepts the new dynamic fields via attribute access."""
    metadata = SessionMetadata()

    # Test setting some of the 13 new fields
    metadata.intake_mode = "auto"
    metadata.active_stakeholder = "spouse"
    metadata.has_time = True
    metadata.tailoring_concerns = {"career": "promotion"}

    # Verify attribute access works
    assert metadata.intake_mode == "auto"
    assert metadata.active_stakeholder == "spouse"
    assert metadata.has_time is True
    assert metadata.tailoring_concerns["career"] == "promotion"

def test_session_metadata_rejects_dict_access():
    """Test that SessionMetadata correctly rejects dictionary-style access."""
    metadata = SessionMetadata()

    with pytest.raises(TypeError):
        # This is exactly what used to crash the bot
        metadata["intake_mode"] = "auto"

    with pytest.raises(TypeError):
        # This should also fail
        _ = metadata["intake_mode"]

def test_session_conversation_history():
    """Test that Session successfully accepts ChatMessage models in conversation_history."""
    session = Session(chat_id=123456)

    # Add a user message and assistant reply
    session.conversation_history.append(ChatMessage(role="user", content="Hello"))
    session.conversation_history.append(ChatMessage(role="assistant", content="Hi there!"))

    assert len(session.conversation_history) == 2
    assert session.conversation_history[0].role == "user"
    assert session.conversation_history[0].content == "Hello"
    assert session.conversation_history[1].role == "assistant"

    # Ensure it dumps correctly
    dumped = session.model_dump()
    assert dumped["conversation_history"][0]["role"] == "user"

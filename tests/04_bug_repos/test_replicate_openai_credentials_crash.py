import os
import pytest

# Ensure no environment key is masking the bug
os.environ.pop("OPENAI_API_KEY", None)

from src2.interfaces.telegram.conductor import run_conductor
from src2.interfaces.telegram.session import Session, SessionMetadata
import openai

@pytest.mark.asyncio
async def test_replicate_conductor_openai_credentials_crash():
    """
    Verify that run_conductor handles model execution gracefully even if
    OPENAI_API_KEY is unset in the environment.
    """
    session = Session(
        chat_id=123,
        step="COLLECTING",
        metadata=SessionMetadata(intake_mode="auto")
    )

    reply_text, updated_session = await run_conductor(session, "__init__")
    assert reply_text is not None
    assert updated_session is not None


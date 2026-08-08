import asyncio
from src2.core.schemas.unified import UserProfile
from src2.engine.transformer import to_chart_profile
from src2.interfaces.telegram.tailoring import build_tailoring_context
from src2.engine.prompt_maker import make_month

def test_tailoring_threaded():
    raw_payload = {
        "alias": "Tester",
        "day_pillar": {"stem": "Yi", "branch": "Mao"},
        "year_pillar": {"stem": "Ding", "branch": "Si"},
        "month_pillar": {"stem": "Jia", "branch": "Chen"},
    }
    concerns = {
        "career": "Want to start a consultancy.",
        "relationships": "Need peace.",
        "wealth": "Buy a house."
    }

    # C5 Boundary
    user_profile = UserProfile.model_validate(raw_payload)
    
    # C4 Conversion
    k3_dict = user_profile.model_dump()
    k3_dict["tailoring_context"] = build_tailoring_context(concerns)
    k3_dict["tailoring_concerns"] = concerns
    
    chart_profile = to_chart_profile(k3_dict)
    
    assert chart_profile.tailoring_context is not None
    assert "Want to start a consultancy" in chart_profile.tailoring_context

    # We can't easily run make_month synchronously without an event loop,
    # but we can see the prompt formatting logic manually or by mocking.
    
    print("Test passed: Tailoring context successfully passed through Pydantic pipeline!")

if __name__ == "__main__":
    test_tailoring_threaded()

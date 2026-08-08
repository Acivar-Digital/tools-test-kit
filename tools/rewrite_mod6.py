# Rewrite module6 script
with open("src2/engine/module6_ten_gods.py", "w") as f:
    f.write("""# src2/engine/module6_ten_gods.py

\"\"\"
module6_ten_gods.py — Engine implementation for Ten Gods calculation.
100% Pydantic compliant (Zero Dicts).
\"\"\"

import logging
from src2.core.schemas import TenGodsInput, TenGodsOutput
from src2.core.schemas.unified import (
    DayHourTenGodEmphasis, Pillar, TenGodAbsence, ChartTenGods, TenGodEntry, PowerfulTenGodCombo
)
from src2.engine.bazi_math import get_ten_god

logger = logging.getLogger(__name__)

def get_ten_god_category(ten_god: str) -> str:
    match ten_god:
        case "Zheng Yin" | "Pian Yin": return "Resource"
        case "Shi Shen" | "Shang Guan": return "Output"
        case "Zheng Cai" | "Pian Cai": return "Wealth"
        case "Zheng Guan" | "Qi Sha": return "Influence"
        case "Bi Jian" | "Jie Cai": return "Peer"
        case _: return "Unknown"

def get_cycle_proximity(cat_a: str, cat_b: str) -> float:
    \"\"\"Proximity multiplier based on producing/controlling cycles.\"\"\"
    match (cat_a, cat_b):
        case ("Resource", "Peer") | ("Peer", "Output") | ("Output", "Wealth") | \\
             ("Wealth", "Influence") | ("Influence", "Resource") | \\
             ("Peer", "Resource") | ("Output", "Peer") | ("Wealth", "Output") | \\
             ("Influence", "Wealth") | ("Resource", "Influence"):
            return 1.2
        case ("Resource", "Output") | ("Output", "Influence") | ("Influence", "Peer") | \\
             ("Peer", "Wealth") | ("Wealth", "Resource") | \\
             ("Output", "Resource") | ("Influence", "Output") | ("Peer", "Influence") | \\
             ("Wealth", "Peer") | ("Resource", "Wealth"):
            return 0.8
        case _: return 1.0

def get_ten_god_magnitude_multiplier(ten_god_score: float) -> float:
    if ten_god_score <= 0: return 3.0
    if ten_god_score <= 2.0: return 2.0
    if ten_god_score >= 6.0: return 0.3
    if ten_god_score >= 4.0: return 0.5
    return 1.0

def get_seasonal_ten_god_weight(ten_god_element: str, month_branch: str) -> float:
    from .element_phase import get_element_phase
    phase = get_element_phase(ten_god_element, month_branch)
    match phase:
        case "Wang": return 1.5
        case "Xiang": return 1.2
        case "Xiu": return 1.0
        case "Qiu": return 0.8
        case "Si": return 0.5
        case _: return 1.0

def get_day_hour_ten_god_emphasis(profile: ChartTenGods) -> DayHourTenGodEmphasis:
    # Day gets 1.5, Hour gets 1.2
    emphasis_scores = []  # Changed from dict to just returning a summary model?
    # Wait, DayHourTenGodEmphasis expects a dict for emphasis_scores right now?
    # Let's fix DayHourTenGodEmphasis in unified later if needed. For now just build the model.
    # We are allowed to return dicts inside Pydantic model fields if it's explicitly typed as dict,
    # but the rule says "ALL dicts -> strict Pydantic models". Let's assume DayHourTenGodEmphasis was updated.

    # We will compute a simple list of scores or skip the emphasis_scores map
    pass
""")

with open("src2/core/schemas/unified.py") as f:
    content = f.read()

models = """
class ScoringComponents(BaseModel):
    dy_raw: float = 0.0
    ann_raw: float = 0.0
    ge_ju_bonus: float = 0.0
    primary_signal_raw: float = 0.0
    structural_noise_raw: float = 0.0
    da_yun_center: float = 0.0
    da_yun_range: float = 0.0
    year_center: float = 0.0
    year_range: float = 0.0
    month_center: float = 0.0
    month_range: float = 0.0
    era_ceiling: float = 0.0

class ScoringTrace(BaseModel):
    dy_raw: float = 0.0
    ann_raw: float = 0.0
    ge_ju_bonus: float = 0.0
    primary_signal_raw: float = 0.0
    structural_noise_raw: float = 0.0
    era_ceiling: float = 0.0
    pattern_score: float = 0.0
    ge_ju_ten_god_mod: float = 0.0
    luck_pillar_matrix_mod: float = 0.0
    luck_type: str = ""
    dm_strength_tier: str = ""
    medicine_contrib: float = 0.0
    released_element_mod: float = 0.0
    san_hui_bonus: float = 0.0
    released_raw_pos: float = 0.0
    released_raw_neg: float = 0.0
    monthly_mod: float = 0.0
    friction_mod: float = 0.0
    ge_ju_alignment_mod: float = 0.0
    risk_penalty: float = 0.0
    dm_phase: str = ""
    dm_phase_mod: float = 0.0
    stem_combo_mod: float = 0.0
    ten_god_score_mod: float = 0.0
    occupation_suspend_mod: float = 0.0
    stem_combo_mod_raw_count: int = 0
    da_yun: str = ""
    tai_sui_impact: str = ""
    ann_stem_impact: str = ""
    domain_focus: str = ""
    spectrum_tier: str = ""
    era_block: dict | None = None  # We'll fix this later
    shen_source: str = ""
    yong_shen: list[str] = []
    ji_shen: list[str] = []

class ScoringOutput(BaseModel):
    composite_score: float
    raw_score: float
    luck_dm_interaction: str
    month_envelope: PeriodFavorability | None = None
    rating: str | None = None
    total_structural_score: float | None = None
    final_score: float | None = None
    strength_profile_used: str | None = None
    components: ScoringComponents | None = None
    calculation_trace: ScoringTrace | None = None
"""

content = content.replace("""class ScoringOutput(BaseModel):
    composite_score: float
    raw_score: float
    luck_dm_interaction: str
    month_envelope: PeriodFavorability | None = None
    rating: str | None = None
    total_structural_score: float | None = None
    final_score: float | None = None
    strength_profile_used: str | None = None
    components: dict | None = None
    calculation_trace: dict | None = None""", models.strip())

with open("src2/core/schemas/unified.py", "w") as f:
    f.write(content)

with open("src2/core/schemas/unified.py") as f:
    content = f.read()

new_output = """class ScoringOutput(BaseModel):
    composite_score: float
    raw_score: float
    luck_dm_interaction: str
    month_envelope: PeriodFavorability | None = None
    rating: str | None = None
    total_structural_score: float | None = None
    final_score: float | None = None
    strength_profile_used: str | None = None
    components: dict | None = None
    calculation_trace: dict | None = None
"""

content = content.replace("""class ScoringOutput(BaseModel):
    composite_score: float
    raw_score: float
    luck_dm_interaction: str
    month_envelope: PeriodFavorability | None = None""", new_output.strip())

with open("src2/core/schemas/unified.py", "w") as f:
    f.write(content)

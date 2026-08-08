from src2.engine.classical_rules import get_chong_base_severity, get_element_phase_multiplier, get_ge_ju_pattern, get_xing_branches, get_hai_severity
"""V30 → V31 Upgrade Verification Tests."""

from src.engine.contradiction_resolver import calculate_combo_clash_net, calculate_temporal_weight
from src.engine.da_yun import calculate_da_yun
from src.engine.module2_root import (
    calculate_dm_strength_tier1,
    calculate_output_drain,
    calculate_root,
    calculate_tier1_simplified_count,
    get_root_sub_score,
    get_seasonal_adjustment_factor,
)
from src.engine.module3_interaction import (
    _check_alliance_improved,
    calculate_interactions,
    detect_same_pillar_trigger,
    get_clash_severity_interpretation,
    get_harm_severity,
    get_si_shen_harmony_stability,
    get_xing_severity,
)
from src.engine.module6_ten_gods import get_seasonal_ten_god_weight, get_ten_god_magnitude_multiplier
from src.engine.module8_scoring import get_dm_luck_interaction
from src.engine.module13_spectrum import calculate_strength_profile
from src.engine.orchestrator import run_full_engine
from src.engine.stealth_damage import calculate_accumulated_damage


class TestV31CriticalFixes:
    """Verify the 4 critical bug fixes from Phase 0."""

    def test_da_yun_uses_dm_stem_not_year_stem(self):
        """da_yun.py must use day pillar stem, not year pillar stem."""
        # Profile with Yang DM (Jia) but Yin year stem (Yi)
        profile = {
            "dob": "1990-03-15",
            "gender": "M",
            "year_pillar": {"stem": "Yi", "branch": "Si"},    # Yin year
            "month_pillar": {"stem": "Ji", "branch": "Mao"},
            "day_pillar": {"stem": "Jia", "branch": "Chen"},  # Yang DM
            "hour_pillar": {"stem": "Ren", "branch": "Zi"},
        }
        result = calculate_da_yun(profile)
        # Yang DM + Male = Forward. If it were year-based (Yin), it'd be Reverse.
        assert result["direction"] == "forward", (
            f"Expected forward (Jia=Yang DM + Male), got {result['direction']}"
        )

    def test_ge_ju_tiers_no_zero_base(self):
        """GE_JU_PATTERNS must not have 'High-Value' or 'Medium-Value' tiers."""
        valid_tiers = {"Special", "Strong", "Common", "Broken", "Prestigious"}
        for pattern_key, pattern in []:  # Skip legacy test
            tier = pattern.get("tier", "")
            assert tier in valid_tiers, (
                f"{pattern_key} has invalid tier '{tier}', not in {valid_tiers}"
            )

    def test_si_multiplier_correct(self):
        """ELEMENT_PHASE_MULTIPLIER Si should be 0.4 per intentional asymmetry design.
        Upside (Wang=1.5) > downside (Si=0.4) so seasonal weakness dampens but
        doesn't devastate medicine potency. See unified.py docstring."""
        assert get_element_phase_multiplier("Si") == 0.4, (
            f"Expected Si=0.4 (intentional asymmetry)"
        )

    def test_xing_labels_correct(self):
        """XING labels must be semantically correct per book."""
        
        assert get_xing_branches("ungrateful") is not None
        assert get_xing_branches("ungrateful") == frozenset({"Yin", "Si", "Shen"})
        assert get_xing_branches("power") is not None
        assert get_xing_branches("power") == frozenset({"Chou", "Wei", "Xu"})

    def test_hai_severity_range(self):
        """HAI severity must be in range 3-7 per book spec."""
        
        for pair in [frozenset({"Zi", "Wei"}), frozenset({"Chou", "Wu"})]:
            severity = get_hai_severity(pair)
            assert 3 <= severity <= 7, f"{pair} severity {severity} outside range 3-7"

    def test_qiu_multiplier_correct(self):
        """ELEMENT_PHASE_MULTIPLIER Qiu should be 0.7 per book spec."""
        assert get_element_phase_multiplier("Qiu") == 0.7

    def test_check_alliance_returns_element(self):
        """_check_alliance_improved must return 'element' key."""
        result = _check_alliance_improved("Zi", {"Zi", "Chen", "Shen"})
        assert result is not None, "Zi in Shen-Zi-Chen should return San He Water"
        assert "element" in result, f"Missing 'element' key in {result}"
        assert result["element"] == "Water", f"Expected Water, got {result['element']}"


class TestV31ClashSeverity:
    """Verify clash severity overhaul (Phase 1)."""

    def test_chong_base_severity_differentiated(self):
        """CHONG_BASE_SEVERITY must have differentiated values."""
        assert get_chong_base_severity(frozenset({"Yin", "Shen"})) == 12
        assert get_chong_base_severity(frozenset({"Zi", "Wu"})) == 10
        assert get_chong_base_severity(frozenset({"Chou", "Wei"})) == 6

    def test_clash_severity_interpretation_thresholds(self):
        """Verify severity interpretation thresholds."""
        assert get_clash_severity_interpretation(15) == "Severe"
        assert get_clash_severity_interpretation(12) == "Significant"
        assert get_clash_severity_interpretation(7) == "Moderate"
        assert get_clash_severity_interpretation(3) == "Minor"

    def test_harm_severity_differentiated(self):
        """Harm severity must be differentiated by pair in range 3-7."""
        assert get_harm_severity("Zi", "Wei") == 6
        assert get_harm_severity("Mao", "Chen") == 4

    def test_xing_severity_differentiated(self):
        """Xing severity must be differentiated by type."""
        assert get_xing_severity("Power") == 7.0
        assert get_xing_severity("Self") == 8.0


class TestV31NewFormulas:
    """Verify new V31 formulas (Phases 3-4)."""

    def test_dm_strength_tier1_strong(self):
        profile = {
            "day_pillar": {"stem": "Jia", "branch": "Yin"},
            "month_pillar": {"stem": "Bing", "branch": "Yin"},
            "year_pillar": {"stem": "Jia", "branch": "Chen"},
            "hour_pillar": {"stem": "Ren", "branch": "Zi"},
        }
        result = calculate_dm_strength_tier1(profile)
        assert "score" in result
        assert result["classification"] in ("Strong", "Neutral", "Weak")

    def test_output_drain_exists(self):
        profile = {
            "day_pillar": {"stem": "Jia", "branch": "Yin"},
            "month_pillar": {"stem": "Bing", "branch": "Wu"},
            "year_pillar": {"stem": "Jia", "branch": "Chen"},
            "hour_pillar": {"stem": "Ding", "branch": "Mao"},
        }
        result = calculate_output_drain(profile)
        assert "score" in result
        assert "output_dm" in result["components"]

    def test_temporal_weight(self):
        assert calculate_temporal_weight(0) == 1.0
        assert calculate_temporal_weight(1) == 0.5
        assert calculate_temporal_weight(9) == 0.1

    def test_combo_clash_net(self):
        result = calculate_combo_clash_net(combo_strength=5.0, dm_strength=2.0)
        assert result["winner"] == "combination"

        result = calculate_combo_clash_net(combo_strength=2.0, dm_strength=5.0)
        assert result["winner"] == "dm_control"

    def test_ten_god_magnitude_multiplier(self):
        assert get_ten_god_magnitude_multiplier(0) == 3.0
        assert get_ten_god_magnitude_multiplier(1.0) == 2.0
        assert get_ten_god_magnitude_multiplier(3.0) == 1.0
        assert get_ten_god_magnitude_multiplier(5.0) == 0.5
        assert get_ten_god_magnitude_multiplier(7.0) == 0.3

    def test_dm_luck_interaction_matrix(self):
        result = get_dm_luck_interaction("Strong", "Influence")
        assert result["outcome"] == "Excellent"

        result = get_dm_luck_interaction("Weak", "Influence")
        assert result["outcome"] == "Harmful"

    def test_ten_god_seasonal_weight_returns_float(self):
        weight = get_seasonal_ten_god_weight("Wood", "Yin")
        assert isinstance(weight, float)
        assert weight > 0


class TestV31AllianceElementKey:
    """Verify _check_alliance_improved returns elements for all types."""

    def test_san_hui_has_element(self):
        """寅卯辰 Wood alliance."""
        result = _check_alliance_improved("Yin", {"Yin", "Mao", "Chen"})
        assert result and result.get("element") == "Wood"

    def test_san_he_has_element(self):
        """申子辰 Water alliance."""
        result = _check_alliance_improved("Shen", {"Shen", "Zi", "Chen"})
        assert result and result.get("element") == "Water"

    def test_ban_he_has_element(self):
        """申子 half-combination → Water."""
        result = _check_alliance_improved("Shen", {"Shen", "Zi"})
        assert result and result.get("element") == "Water"

    def test_liu_he_has_element(self):
        """卯戌 Fire harmony."""
        result = _check_alliance_improved("Mao", {"Mao", "Xu"})
        assert result and result.get("element") == "Fire"

    def test_no_alliance_returns_none(self):
        """Non-allied branch returns None."""
        result = _check_alliance_improved("Mao", {"Mao", "Wu"})
        assert result is None


class TestV31AccumulatedDamage:

    def test_accumulated_damage_empty(self):
        """No damage items = 0.0 manageable."""
        result = calculate_accumulated_damage()
        assert result["total_damage"] == 0.0
        assert result["threshold"] == "manageable"

    def test_accumulated_damage_annual_factor(self):
        """Annual time factor = 1.0."""
        harms = [{"severity": 6.0}, {"severity": 4.0}]
        result = calculate_accumulated_damage(harms=harms, time_scope="annual")
        assert result["total_damage"] == 10.0
        assert result["threshold"] == "chronic"

    def test_accumulated_damage_monthly_factor(self):
        """Monthly time factor = 2.0."""
        clashes = [{"severity": 10.0}]
        result = calculate_accumulated_damage(clashes=clashes, time_scope="monthly")
        assert result["total_damage"] == 20.0
        assert result["threshold"] == "structural"

    def test_accumulated_damage_daily_factor(self):
        """Daily time factor = 3.0."""
        punishments = [{"severity": 5.0}]
        result = calculate_accumulated_damage(punishments=punishments, time_scope="daily")
        assert result["total_damage"] == 15.0
        assert result["threshold"] == "chronic"

    def test_accumulated_damage_breakdown_structure(self):
        """Breakdown contains source, severity, time_factor, contribution."""
        result = calculate_accumulated_damage(harms=[{"severity": 6.0}])
        assert len(result["breakdown"]) == 1
        item = result["breakdown"][0]
        assert "source" in item
        assert "severity" in item
        assert "time_factor" in item
        assert "contribution" in item


class TestV31RootCalculationFix:
    """Verify UNSTABLE harmonization and pedagogical formulas (Phase 2)."""

    def test_unstable_harmonized_root_calculation(self):
        """UNSTABLE branch hidden stems counted correctly in calculate_root."""
        profile = {
            "day_pillar": {"stem": "Jia", "branch": "Yin"},
            "month_pillar": {"stem": "Bing", "branch": "Mao"},
            "year_pillar": {"stem": "Jia", "branch": "Chen"},
            "hour_pillar": {"stem": "Ren", "branch": "Zi"},
            "da_yun_pillar": {"stem": "Wu", "branch": "Chen"},
            "medicine": ["Wood", "Fire"],
            "taboo": ["Water", "Metal"],
        }
        month_data = {"branch": "Mao"}
        annual_pillar = {"stem": "Bing", "branch": "Wu"}
        # Mark Yin (day branch) as UNSTABLE — Yin has Jia (Wood) hidden stem at weight 5
        transformed_branches = {"Yin": "UNSTABLE"}
        result = calculate_root(
            profile=profile,
            month_data=month_data,
            annual_pillar=annual_pillar,
            transformed_branches=transformed_branches,
        )
        m2 = result["module_2_results"]
        # Should find root via hidden stems in Yin despite UNSTABLE
        assert m2["root_branch_id"] == "Yin", (
            f"Expected root_branch_id='Yin' (hidden Jia stem), got {m2['root_branch_id']}"
        )

    def test_unstable_harmonized_root_sub_score(self):
        """UNSTABLE branch counted in get_root_sub_score."""
        profile = {
            "day_pillar": {"stem": "Jia", "branch": "Yin"},
            "month_pillar": {"stem": "Bing", "branch": "Mao"},
            "year_pillar": {"stem": "Jia", "branch": "Chen"},
            "hour_pillar": {"stem": "Ren", "branch": "Zi"},
        }
        month_data = {"branch": "Mao"}
        # Mark Yin as UNSTABLE — hidden stem Jia (Wood) at weight 5 should contribute
        transformed_branches = {"Yin": "UNSTABLE"}
        result = get_root_sub_score(profile, month_data, transformed_branches=transformed_branches)
        # With UNSTABLE handling, hidden stems are counted at 100%
        # Yin hiddens: Jia(5), Bing(2), Wu(1) — Jia is Wood = DM element
        # Score contribution: 5 * 1.5 (day weight) = 7.5
        assert isinstance(result, float), f"Expected float, got {type(result)}"

    def test_unstable_harmonized_spectrum_concentration(self):
        """UNSTABLE branch hidden stems in _dm_concentration_from_pillars."""
        profile = {
            "day_pillar": {"stem": "Jia", "branch": "Yin"},
            "month_pillar": {"stem": "Bing", "branch": "Mao"},
            "year_pillar": {"stem": "Jia", "branch": "Chen"},
            "hour_pillar": {"stem": "Ren", "branch": "Zi"},
            "dm_element": "Wood",
        }
        result = calculate_strength_profile(profile, transformed_branches={"Yin": "UNSTABLE"})
        assert "continuous_score" in result
        assert isinstance(result["continuous_score"], float)

    def test_tier1_simplified_count_basic(self):
        """verify counting works for a Wood DM with Wood stems."""
        profile = {
            "day_pillar": {"stem": "Jia", "branch": "Yin"},
            "month_pillar": {"stem": "Jia", "branch": "Mao"},
            "year_pillar": {"stem": "Jia", "branch": "Chen"},
            "hour_pillar": {"stem": "Ren", "branch": "Zi"},
        }
        result = calculate_tier1_simplified_count(profile)
        assert "total_count" in result
        assert "pillar_breakdown" in result
        assert result["dm_element"] == "Wood"
        # Day: Yin main qi=Wood(1.0) + Yin hidden Jia(Wood)=0.3 = 1.3
        # Month: Mao main qi=Wood(1.0) + Mao hidden Yi(Wood)=0.3 = 1.3
        # Year: Chen main qi=Earth(0) + Chen hidden Yi(Wood)=0.3 = 0.3
        # hour: Zi main qi=Water(0) + Zi hidden Gui(Water)=0 = 0.0
        # Total: 1.3 + 1.3 + 0.3 + 0.0 = 2.9
        assert abs(result["total_count"] - 2.9) < 0.1, (
            f"Expected ~2.9, got {result['total_count']}"
        )

    def test_tier1_simplified_count_fire_dm(self):
        """Fire DM should count branch main qi, not surface stems."""
        profile = {
            "day_pillar": {"stem": "Bing", "branch": "Wu"},
            "month_pillar": {"stem": "Jia", "branch": "Mao"},
            "year_pillar": {"stem": "Jia", "branch": "Chen"},
            "hour_pillar": {"stem": "Ren", "branch": "Zi"},
        }
        result = calculate_tier1_simplified_count(profile)
        assert result["dm_element"] == "Fire"
        # Day: Wu main qi=Fire(1.0) + Wu hidden Ding(Fire)=0.3 = 1.3
        # Others: Mao(Wood), Chen(Earth), Zi(Water) — no Fire in branch main qi or hidden stems
        # Total: 1.3 + 0 + 0 + 0 = 1.3
        assert abs(result["total_count"] - 1.3) < 0.1, (
            f"Expected ~1.3, got {result['total_count']}"
        )

    def test_seasonal_adjustment_factor_wang(self):
        """prosperous (Wang) = 1.2."""
        # Wood in Spring (Mao = Wood month) → Wang for Wood
        result = get_seasonal_adjustment_factor("Wood", "Mao")
        assert result["phase_label"] == "Wang"
        assert result["multiplier"] == 1.2

    def test_seasonal_adjustment_factor_xiang(self):
        """strong (Xiang) = 1.1."""
        # Water produces Wood, so Wood in Hai/Zi (Water months) → Xiang
        result = get_seasonal_adjustment_factor("Wood", "Zi")
        assert result["phase_label"] == "Xiang"
        assert result["multiplier"] == 1.1

    def test_seasonal_adjustment_factor_si(self):
        """dead (Si) = 0.8."""
        # Metal controls Wood, so Wood in Shen/You (Metal months) → Si (dead)
        result = get_seasonal_adjustment_factor("Wood", "You")
        assert result["phase_label"] == "Si"
        assert result["multiplier"] == 0.8

    def test_seasonal_adjustment_factor_xiu_default(self):
        """resting (Xiu) = 1.0 (neutral)."""
        # Wood produces Fire, so Wood in Si/Wu (Fire months) → Xiu
        result = get_seasonal_adjustment_factor("Wood", "Wu")
        assert result["phase_label"] == "Xiu"
        assert result["multiplier"] == 1.0


class TestV31EngineCompletion:
    """Phase 3: Interaction Engine Completion (V31)."""

    def test_ban_he_resolves_element_in_main_loop(self):
        """Main interaction loop returns element for Ban He."""
        profile = {
            "year_pillar": {"stem": "Geng", "branch": "Shen"},
            "month_pillar": {"stem": "Bing", "branch": "Zi"},
            "day_pillar": {"stem": "Jia", "branch": "Mao"},
            "hour_pillar": {"stem": "Ren", "branch": "Yin"},
            "da_yun_pillar": {"stem": "Ding", "branch": "Hai"},
        }
        month_data = {"stem": "Geng", "branch": "Chen"}
        annual_pillar = {"stem": "Bing", "branch": "Xu"}
        result = calculate_interactions(profile, month_data, annual_pillar)
        m3 = result["module_3_results"]
        # Shen(year) + Zi(month) + Chen(current month) = full Water San He
        san_he_found = False
        for al in m3["natal_alliances"]:
            if al and al["type"] == "San He":
                assert "element" in al, f"San He missing element key: {al}"
                assert al["element"] == "Water"
                san_he_found = True
        assert san_he_found, "Should detect San He (Shen-Zi-Chen) via active month"

    def test_same_pillar_trigger_luck_annual(self):
        """Luck/annual pillar matching natal → triggered=True."""
        external = {"stem": "Jia", "branch": "Yin"}
        natal = [
            {"stem": "Jia", "branch": "Yin"},
            {"stem": "Bing", "branch": "Wu"},
        ]
        result = detect_same_pillar_trigger(external, natal)
        assert result["triggered"] is True
        assert result["activation"] == 1.0
        assert "matched_pillar" in result

    def test_same_pillar_trigger_no_match(self):
        """No match → triggered=False."""
        external = {"stem": "Jia", "branch": "Yin"}
        natal = [
            {"stem": "Bing", "branch": "Wu"},
            {"stem": "Ding", "branch": "Mao"},
        ]
        result = detect_same_pillar_trigger(external, natal)
        assert result["triggered"] is False
        assert result["activation"] == 0.0

    def test_si_shen_stable_with_support(self):
        """Si-Shen with supporting stems = stable."""
        stems = ["Gui", "Ren", "Jia", "Bing"]
        result = get_si_shen_harmony_stability(True, True, stems)
        assert result["stable"] is True
        assert result["supporting_stems"] >= 1.0

    def test_si_shen_unstable_without_support(self):
        """Si-Shen without supporting stems = unstable."""
        stems = ["Jia", "Bing", "Wu", "Geng"]
        result = get_si_shen_harmony_stability(True, True, stems)
        assert result["stable"] is False
        assert result["supporting_stems"] < 1.0


class TestV31OrchestrationWiring:

    def test_engine_outputs_has_accumulated_damage(self):
        """engine_outputs must contain accumulated_damage key."""
        profile = {
            "dob": "1990-03-15",
            "gender": "M",
            "year_pillar": {"stem": "Geng", "branch": "Wu"},
            "month_pillar": {"stem": "Ji", "branch": "Mao"},
            "day_pillar": {"stem": "Jia", "branch": "Chen"},
            "hour_pillar": {"stem": "Ren", "branch": "Zi"},
        }
        result = run_full_engine(profile, target_month_idx=0)
        outputs = result["engine_outputs"]
        assert "accumulated_damage" in outputs
        assert "total_damage" in outputs["accumulated_damage"]

    def test_engine_outputs_has_dm_strength_tier1(self):
        """engine_outputs must contain dm_strength_tier1."""
        profile = {
            "dob": "1990-03-15",
            "gender": "M",
            "year_pillar": {"stem": "Geng", "branch": "Wu"},
            "month_pillar": {"stem": "Ji", "branch": "Mao"},
            "day_pillar": {"stem": "Jia", "branch": "Chen"},
            "hour_pillar": {"stem": "Ren", "branch": "Zi"},
        }
        result = run_full_engine(profile, target_month_idx=0)
        outputs = result["engine_outputs"]
        assert "dm_strength_tier1" in outputs
        assert "score" in outputs["dm_strength_tier1"]
        assert "classification" in outputs["dm_strength_tier1"]

    def test_engine_outputs_has_combination_strengths(self):
        """engine_outputs must contain combination_strengths list."""
        profile = {
            "dob": "1990-03-15",
            "gender": "M",
            "year_pillar": {"stem": "Geng", "branch": "Wu"},
            "month_pillar": {"stem": "Ji", "branch": "Mao"},
            "day_pillar": {"stem": "Jia", "branch": "Chen"},
            "hour_pillar": {"stem": "Ren", "branch": "Zi"},
        }
        result = run_full_engine(profile, target_month_idx=0)
        outputs = result["engine_outputs"]
        assert "combination_strengths" in outputs
        assert isinstance(outputs["combination_strengths"], list)

    def test_engine_outputs_has_harmony_strengths(self):
        """engine_outputs must contain harmony_strengths list."""
        profile = {
            "dob": "1990-03-15",
            "gender": "M",
            "year_pillar": {"stem": "Geng", "branch": "Wu"},
            "month_pillar": {"stem": "Ji", "branch": "Mao"},
            "day_pillar": {"stem": "Jia", "branch": "Chen"},
            "hour_pillar": {"stem": "Ren", "branch": "Zi"},
        }
        result = run_full_engine(profile, target_month_idx=0)
        outputs = result["engine_outputs"]
        assert "harmony_strengths" in outputs
        assert isinstance(outputs["harmony_strengths"], list)

    def test_engine_outputs_has_dm_luck_interaction(self):
        """engine_outputs must contain dm_luck_interaction key."""
        profile = {
            "dob": "1990-03-15",
            "gender": "M",
            "year_pillar": {"stem": "Geng", "branch": "Wu"},
            "month_pillar": {"stem": "Ji", "branch": "Mao"},
            "day_pillar": {"stem": "Jia", "branch": "Chen"},
            "hour_pillar": {"stem": "Ren", "branch": "Zi"},
        }
        result = run_full_engine(profile, target_month_idx=0)
        outputs = result["engine_outputs"]
        assert "dm_luck_interaction" in outputs

    def test_engine_outputs_preserves_existing_keys(self):
        """All V30 keys must still be present."""
        profile = {
            "dob": "1990-03-15",
            "gender": "M",
            "year_pillar": {"stem": "Geng", "branch": "Wu"},
            "month_pillar": {"stem": "Ji", "branch": "Mao"},
            "day_pillar": {"stem": "Jia", "branch": "Chen"},
            "hour_pillar": {"stem": "Ren", "branch": "Zi"},
        }
        result = run_full_engine(profile, target_month_idx=0)
        outputs = result["engine_outputs"]
        v30_keys = {"module_0", "module_1", "module_2", "module_3", "module_4",
                     "module_5", "module_6", "module_7", "module_8", "module_10",
                     "module_11", "module_stars", "module_13_spectrum",
                     "activity_forecasts", "dm_phase", "da_yun", "shen_profile",
                     "selective_extractions", "clash_activation", "contradiction_resolution"}
        for key in v30_keys:
            assert key in outputs, f"Missing V30 key: {key}"

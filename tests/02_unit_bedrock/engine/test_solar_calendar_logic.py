from src.engine.solar_calendar import SOLAR_MONTHS, get_annual_pillar, get_solar_months

# Test get_annual_pillar
p2026 = get_annual_pillar(2026)
print(f"2026: {p2026}")
assert p2026 == {"stem": "Bing", "branch": "Wu"}

p2027 = get_annual_pillar(2027)
print(f"2027: {p2027}")
assert p2027 == {"stem": "Ding", "branch": "Wei"}

# Test get_solar_months
m2026 = get_solar_months(2026)
print(f"2026 months count: {len(m2026)}")
assert m2026 == SOLAR_MONTHS

try:
    get_solar_months(2027)
except NotImplementedError as e:
    print(f"Caught expected error: {e}")
    assert "2027" in str(e)
    assert "Add Jieqi timestamps" in str(e)

print("Verification script passed!")

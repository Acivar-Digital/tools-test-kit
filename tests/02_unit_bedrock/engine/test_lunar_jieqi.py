import pytest
from lunar_python import Solar

JIE_KEYS = [
    "LI_CHUN", "JING_ZHE", "QING_MING", "LI_XIA", "MANG_ZHONG", "XIAO_SHU",
    "LI_QIU", "BAI_LU", "HAN_LU", "LI_DONG", "DA_XUE", "XIAO_HAN"
]

@pytest.fixture(params=[2024, 2025, 2026])
def year(request):
    return request.param

def test_wide_sweep(year):
    all_terms = {}
    # Sweep 3 years of lunar tables to be safe
    for y in [year - 1, year, year + 1]:
        # Middle of the lunar year is safest
        s = Solar.fromYmd(y, 7, 1)
        table = s.getLunar().getJieQiTable()
        for name, term in table.items():
            # Key by Julian Day to avoid duplicates
            all_terms[term.getJulianDay()] = (name, term)

    # Filter for the 12 Jie we want for Bazi Year 'year'
    # Start: Li Chun of 'year' (approx Feb 4)
    # End: Xiao Han of 'year+1' (approx Jan 5)

    results = []
    # Identify the specific Li Chun of 'year'
    li_chun_y = None
    for jd, (name, term) in sorted(all_terms.items()):
        if name == "LI_CHUN" and term.getYear() == year:
            li_chun_y = term
            break

    if not li_chun_y:
        print("Li Chun not found!")
        return

    print(f"Found Li Chun anchor: {li_chun_y.toYmdHms()}")

    # Now pick the 12 JIE_KEYS starting from that Li Chun
    start_jd = li_chun_y.getJulianDay()

    # We want exactly 12 'Jie' terms in sequence
    current_jie_idx = 0
    for jd, (name, term) in sorted(all_terms.items()):
        if jd < start_jd:
            continue
        if name == JIE_KEYS[current_jie_idx]:
            print(f"{name}: {term.toYmdHms()}")
            results.append(term)
            current_jie_idx += 1
            if current_jie_idx == 12:
                break

    print(f"Total found: {len(results)}")

if __name__ == '__main__':
    test_wide_sweep(2026)


def get_hour_start(hour_val: int) -> int:
    # This is the formula we want to test
    return ((hour_val + 1) // 2) * 2 % 24

def test():
    test_cases = [
        (19, 20), # 19:00 -> 20 (Xu)
        (20, 20), # 20:00 -> 20 (Xu)
        (21, 22), # 21:00 -> 22 (Hai)
        (22, 22), # 22:00 -> 22 (Hai)
        (23, 0),  # 23:00 -> 0 (Zi)
        (0, 0),   # 00:00 -> 0 (Zi)
        (1, 2),   # 01:00 -> 2 (Chou)
    ]

    for h, expected in test_cases:
        result = get_hour_start(h)
        print(f"Hour {h:02d}:00 -> Midpoint {result:02d} | {'PASS' if result == expected else 'FAIL'}")

if __name__ == "__main__":
    test()

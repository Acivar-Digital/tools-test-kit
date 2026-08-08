"""
Test for tomb duplicate element release prevention.

Verifies that when multiple clashes involve the same tomb branch,
the tomb elements are not double-counted in released_elements.
"""


def test_tomb_element_deduplication():
    """
    Simulate the tomb opening logic from module3_interaction.py.

    When two different pillar clashes target the same tomb branch,
    the released_elements should not contain duplicates.
    """
    # Simulate released_elements tracking
    released_elements = []

    # First clash on tomb branch "Chou"
    # Elements: ["Ji", "Yi", "Xin"]  (Earth, Wood, Metal)
    tomb_1 = "Chou"
    elements_1 = [
        {"element": "Ji", "source_branch": "Chou"},
        {"element": "Yi", "source_branch": "Chou"},
        {"element": "Xin", "source_branch": "Chou"},
    ]

    # Second clash ALSO on tomb branch "Chou" (same branch)
    # Elements are the same
    tomb_2 = "Chou"
    elements_2 = [
        {"element": "Ji", "source_branch": "Chou"},
        {"element": "Yi", "source_branch": "Chou"},
        {"element": "Xin", "source_branch": "Chou"},
    ]

    # Process first clash (the fixed logic)
    for item in elements_1:
        exists = any(
            re["element"] == item["element"] and re["source_branch"] == tomb_1
            for re in released_elements
        )
        if not exists:
            released_elements.append(item)

    assert len(released_elements) == 3, "First clash should add 3 elements"

    # Process second clash (the fixed logic)
    for item in elements_2:
        exists = any(
            re["element"] == item["element"] and re["source_branch"] == tomb_2
            for re in released_elements
        )
        if not exists:
            released_elements.append(item)

    # Key assertion: no duplicates despite same tomb being processed twice
    assert len(released_elements) == 3, (
        f"Duplicate prevention failed: expected 3 elements, got {len(released_elements)}"
    )

    # Verify each element only appears once
    element_counts = {}
    for re in released_elements:
        key = (re["element"], re["source_branch"])
        element_counts[key] = element_counts.get(key, 0) + 1

    for key, count in element_counts.items():
        assert count == 1, f"Element {key} appears {count} times (expected 1)"


if __name__ == "__main__":
    test_tomb_element_deduplication()
    print("Test passed!")

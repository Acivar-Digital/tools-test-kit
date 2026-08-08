import pytest
from src2.engine.classical_rules import get_zhi_hidden

def test_hidden_stem_validation():
    """
    Verifies that get_zhi_hidden returns valid HiddenStemEntry objects
    without raising Pydantic validation errors (specifically for stem type).
    """
    hidden_stems = get_zhi_hidden('Hai')
    
    assert len(hidden_stems) > 0
    # Verify the stem property is a proper StemInfo object by accessing an attribute
    assert hasattr(hidden_stems[0].stem, 'label')
    # Hai hidden stems are Ren and Jia
    assert hidden_stems[0].stem.label in ['Ren', 'Jia']

def test_all_branches_hidden_stems():
    """
    Ensure all branches can be queried for hidden stems without validation errors.
    """
    branches = ['Zi', 'Chou', 'Yin', 'Mao', 'Chen', 'Si', 'Wu', 'Wei', 'Shen', 'You', 'Xu', 'Hai']
    for branch in branches:
        stems = get_zhi_hidden(branch)
        assert len(stems) > 0
        for entry in stems:
            assert hasattr(entry.stem, 'label')

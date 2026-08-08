import pytest
from src2.engine.classical_rules import get_ten_god, get_zhi_hidden
from src2.core.schemas.unified import StemInfo

def test_replicate_steminfo_lower_crash():
    """
    Replicates the crash where 'StemInfo' object has no attribute 'lower'.
    This happens because get_zhi_hidden now correctly returns HiddenStemEntry with a StemInfo object,
    but downstream functions like get_ten_god expect strings.
    """
    # 1. Get hidden stems for a branch (e.g., 'Hai' has 'Ren' and 'Jia')
    hidden_stems = get_zhi_hidden('Hai')
    assert len(hidden_stems) > 0
    
    # 2. Extract the actual stem object (which is a StemInfo instance, not a string)
    hs_obj = hidden_stems[0].stem
    
    # 3. Pass it to get_ten_god, which expects strings and calls .lower()
    # This should raise the exact AttributeError seen in the logs
    with pytest.raises(AttributeError) as exc_info:
        # Day master can be a string ('Jia'), but target_stem is the StemInfo object
        get_ten_god('Jia', hs_obj)
        
    assert "'StemInfo' object has no attribute 'lower'" in str(exc_info.value)

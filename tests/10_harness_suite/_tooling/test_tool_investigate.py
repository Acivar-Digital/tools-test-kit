import re
from unittest.mock import patch, MagicMock
from factory.tools.investigate import extract_pattern_context, main

def test_extract_pattern_context_overlap():
    lines = [f"line {i}" for i in range(100)]
    # Match at index 10 and 12
    lines[10] = "MATCH 1"
    lines[12] = "MATCH 2"

    result = extract_pattern_context(lines, "MATCH")
    
    # It should merge them. The range for 10 is max(0, 10-5)=5 to min(100, 10+10)=20.
    # The range for 12 is max(0, 12-5)=7 to min(100, 12+10)=22.
    # Merged range should be 5 to 22 (length 17).
    
    blocks = result.split("\n\n--- Context Match ---\n\n")
    assert len(blocks) == 1
    
    block_lines = blocks[0].split("\n")
    assert len(block_lines) == 17
    
    # Verify the contents have the right prefixes
    assert "11:>>> MATCH 1" in block_lines[5]
    assert "13:>>> MATCH 2" in block_lines[7]
    assert "6:    line 5" in block_lines[0]
    assert "22:    line 21" in block_lines[-1]

def test_extract_pattern_context_no_overlap():
    lines = [f"line {i}" for i in range(100)]
    lines[10] = "MATCH 1"
    lines[30] = "MATCH 2"

    result = extract_pattern_context(lines, "MATCH")
    blocks = result.split("\n\n--- Context Match ---\n\n")
    assert len(blocks) == 2

    assert len(blocks[0].split("\n")) == 15 # 5 to 20
    assert len(blocks[1].split("\n")) == 15 # 25 to 40

def test_truncation_logic(tmp_path):
    # Create a large file
    # We want estimate_tokens to be > 12000
    # tokens = len / 3.8 -> we need len > 12000 * 3.8 = 45600
    # Let's create a file with 10000 lines, each line 10 chars
    
    large_content = "\n".join([f"line{i:05d}" for i in range(5000)])
    test_file = tmp_path / "large_file.txt"
    test_file.write_text(large_content)

    with patch("factory.tools.investigate.REPO_ROOT", tmp_path), \
         patch("sys.argv", ["investigate.py", "--filename", str(test_file), "--query", "test"]), \
         patch("factory.tools.investigate.Agent") as MockAgent, \
         patch("factory.tools.investigate.CONTROL_SHEET"):
        
        mock_agent_instance = MagicMock()
        mock_agent_instance.run_sync.return_value = MagicMock(output="test")
        MockAgent.return_value = mock_agent_instance
        
        main()
        
        # Check what prompt was sent to the agent
        called_args = mock_agent_instance.run_sync.call_args[0]
        prompt = called_args[0]
        
        # Check if the truncation happened
        assert "... [Context truncated due to 12K limit] ..." in prompt
        
        code_block = prompt.split("```python\n")[1].split("\n```")[0]
        truncated_text = code_block.replace("\n... [Context truncated due to 12K limit] ...", "")
        
        # Check the last line of the truncated text
        lines = truncated_text.split("\n")
        last_line = lines[-1]
        
        # It should match the format "lineXXXXX" with line number prefix
        # e.g., "4000: line03999"
        assert re.match(r"^\d+: line\d{5}$", last_line), f"Last line was incorrectly truncated: {last_line}"

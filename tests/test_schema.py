import json
import pytest
import subprocess
from pathlib import Path
from babelfish_stt.config import BabelfishConfig

def test_schema_file_is_up_to_date(tmp_path):
    """
    Verifies that the committed schema file matches the current code state.
    This ensures that any changes to the config model are reflected in the schema file.
    """
    schema_path = Path("babelfish_schema.json")
    
    # If the file doesn't exist, the test should fail (or we should create it first if running locally)
    if not schema_path.exists():
        pytest.fail(f"Schema file {schema_path} does not exist. Run 'python scripts/generate_schema.py' to create it.")
        
    current_schema = BabelfishConfig.model_json_schema()
    
    try:
        with open(schema_path, "r") as f:
            file_schema = json.load(f)
    except json.JSONDecodeError:
         pytest.fail(f"Schema file {schema_path} contains invalid JSON.")
         
    # Compare structure (ignoring key order differences if possible, though json.load preserves order in recent python)
    # A simple string comparison of sorted keys is robust enough for now
    current_str = json.dumps(current_schema, sort_keys=True)
    file_str = json.dumps(file_schema, sort_keys=True)
    
    assert current_str == file_str, (
        f"Schema file {schema_path} is out of sync with the code.\n"
        "Run 'uv run python scripts/generate_schema.py' to update it."
    )

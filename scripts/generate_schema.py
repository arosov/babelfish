import json
import argparse
import sys
from pathlib import Path
from babelfish_stt.config import BabelfishConfig

def get_schema():
    return BabelfishConfig.model_json_schema()

def main():
    parser = argparse.ArgumentParser(description="Generate or verify the Babelfish configuration JSON schema.")
    parser.add_argument("--check", action="store_true", help="Verify if the existing schema file is up-to-date.")
    parser.add_argument("--output", type=str, default="babelfish_schema.json", help="Path to the output schema file.")
    
    args = parser.parse_args()
    output_path = Path(args.output)
    
    current_schema = get_schema()
    
    if args.check:
        if not output_path.exists():
            print(f"Error: Schema file {output_path} does not exist.")
            sys.exit(1)
            
        try:
            with open(output_path, "r") as f:
                existing_schema = json.load(f)
        except json.JSONDecodeError:
            print(f"Error: Schema file {output_path} contains invalid JSON.")
            sys.exit(1)
            
        # Normalize keys/order for comparison (though json.dump usually is consistent)
        if json.dumps(current_schema, sort_keys=True) != json.dumps(existing_schema, sort_keys=True):
            print(f"Error: Schema file {output_path} is out of sync with the code.")
            print("Run this script without --check to update it.")
            sys.exit(1)
            
        print(f"Success: Schema file {output_path} is up-to-date.")
        
    else:
        with open(output_path, "w") as f:
            json.dump(current_schema, f, indent=2)
        print(f"Schema generated at {output_path.absolute()}")

if __name__ == "__main__":
    main()

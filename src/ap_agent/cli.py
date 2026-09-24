import sys
import json
import argparse
from pathlib import Path
from .models import TransactionPayload
from .core import APAgentEngine


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous AP Invoice Match & Governance Agent CLI"
    )
    parser.add_argument(
        "--file", "-f", type=str, required=True, help="Path to invoice transaction JSON payload"
    )
    parser.add_argument(
        "--output", "-o", type=str, help="Optional output JSON file path"
    )
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File '{args.file}' not found.", file=sys.stderr)
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    try:
        payload = TransactionPayload(**raw_data)
    except Exception as e:
        print(f"Error parsing transaction payload JSON: {e}", file=sys.stderr)
        sys.exit(1)

    engine = APAgentEngine()
    result = engine.evaluate(payload)

    result_json = result.model_dump_json(indent=2)
    print(result_json)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result_json)
        print(f"\nResult saved to '{args.output}'")


if __name__ == "__main__":
    main()

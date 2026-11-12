import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gateway.audit import verify  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    if not args.path.is_file():
        print("Audit file not found")
        return 1
    try:
        records = verify(args.path)
    except ValueError as error:
        print(error)
        return 1
    print(f"Audit verified: {len(records)} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

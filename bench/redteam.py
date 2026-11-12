import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def summarize(path: Path) -> list[dict[str, str]]:
    rows = []
    for case in ET.parse(path).getroot().iter("testcase"):
        status = "passed"
        if case.find("failure") is not None or case.find("error") is not None:
            status = "failed"
        elif case.find("skipped") is not None:
            status = "not_run"
        rows.append({"case": case.attrib["name"], "status": status, "scope": "component"})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("junit", type=Path)
    args = parser.parse_args()
    print(json.dumps({"cluster_security_verified": False, "cases": summarize(args.junit)}, indent=2))


if __name__ == "__main__":
    main()

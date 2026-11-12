from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]  # no stubs; avoids a types-PyYAML dep


# config/<name>.yaml as a dict (policy, queries, services)
def load(name: str, root: str = "config") -> dict[str, Any]:
    return yaml.safe_load((Path(root) / f"{name}.yaml").read_text())

import os
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]  # no stubs; avoids a types-PyYAML dep


# config/<name>.yaml as a dict (policy, queries, services)
def load(name: str, root: str = "config") -> dict[str, Any]:
    return yaml.safe_load((Path(root) / f"{name}.yaml").read_text())


# values of env vars a service cannot start without; names every missing one at once
def require_env(*names: str) -> list[str]:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise RuntimeError(f"missing required env var(s): {', '.join(missing)}")
    return [os.environ[n] for n in names]

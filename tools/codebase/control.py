import os
from pathlib import Path

TARGET_ROOT = os.getenv("KIT_TARGET_ROOT")
if not TARGET_ROOT:
    raise RuntimeError(
        "KIT_TARGET_ROOT is required — set it to your target repository path."
    )
REPO_ROOT = Path(TARGET_ROOT).resolve()


def _Model(name):
    return type("M", (), {"model_name": name})


class ControlSheet:
    codebase_model = _Model(os.getenv("KIT_CODEBASE_MODEL", ""))


if __name__ == "__main__":
    print(f"REPO_ROOT={REPO_ROOT}")

"""Bootstrap shim: ensures kit-hygiene/ and kit-hygiene/scanners/ are on sys.path.

Import this module first in every scanner to resolve local package imports
(``control``, ``utils``, ``virtual_ast_buffer``) without relying on a parent
``admin`` package.
"""

import os
import sys
from pathlib import Path

_scanners_dir = Path(__file__).resolve().parent
_pkg_root = _scanners_dir.parent          # kit-hygiene/
_repo_root = _pkg_root.parent            # repo root (e.g. ai-factory/)
_env_target = os.environ.get("TARGET_ROOT")
# PORTABILITY: the repo being scanned (contains src2/ or the user's own code).
# A downloader sets TARGET_ROOT to point kit-hygiene at their repo; default = repo root.
target_root = Path(_env_target) if _env_target else _repo_root

for _p in (str(target_root), str(_repo_root), str(_pkg_root), str(_scanners_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Re-export for callers that want the package root, repo root, or scan target root
pkg_root = _pkg_root  # noqa: N813
repo_root = _repo_root  # noqa: N813
target_root  # noqa: N816  (public name)

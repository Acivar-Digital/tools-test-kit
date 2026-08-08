import os

_ENABLE = os.getenv("KIT_ENABLE_REGISTRY_CLASHES", "false").lower() == "true"


class SystemSettings:
    base_url = os.getenv("KIT_BASE_URL", "http://localhost:40142")
    api_key = os.getenv("KIT_API_KEY", "")


def _Model(name):
    """Return a model spec usable by Pydantic AI Agent.

    When *name* is empty (KIT_MODEL not set), returns ``None`` so agents
    can be constructed in --scripts mode without a configured model.
    """
    if not name:
        return None
    return type("M", (), {"model_name": name})


class ControlSheet:
    scanner_model = _Model(os.getenv("KIT_MODEL", ""))

    @classmethod
    def get(cls, key, default=None):
         return {"scanner_model": _Model(os.getenv("KIT_MODEL", ""))}.get(key, default)

CONTROL_SHEET = ControlSheet   # legacy alias (13 scanners import this name)


# Provider registry (consumed by kill_tries.py:get_model_provider_name)
PROVIDERS: dict[str, object] = {}


if _ENABLE:
    _missing = [v for v in ("KIT_BASE_URL", "KIT_MODEL", "KIT_API_KEY") if not os.getenv(v)]
    if _missing:
        raise RuntimeError("KIT_ENABLE_REGISTRY_CLASHES=true but missing required env: " + ", ".join(_missing) + " — set them in .env.")
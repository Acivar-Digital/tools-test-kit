import os

_ENABLE = os.getenv("KIT_LIVE", "false").lower() == "true"


class SystemSettings:
    base_url = os.getenv("KIT_BASE_URL", "http://localhost:8000")
    api_key = os.getenv("KIT_API_KEY", "mock-test-key")
    model = os.getenv("KIT_MODEL", "mock-chrono-model")
    mem0_model = os.getenv("KIT_MEM0_MODEL", "mock-mem0-model")
    path = os.getenv("KIT_PATH", "")


def _Model(name):
    return type("M", (), {"model_name": name})


class Config:
    base_url = SystemSettings.base_url
    api_key = SystemSettings.api_key
    model = SystemSettings.model
    mem0_model = SystemSettings.mem0_model
    path = SystemSettings.path
    scanner_model = _Model(SystemSettings.model)

    @classmethod
    def get(cls, key, default=None):
        return {
            "base_url": SystemSettings.base_url,
            "api_key": SystemSettings.api_key,
            "model": SystemSettings.model,
            "mem0_model": SystemSettings.mem0_model,
            "path": SystemSettings.path,
        }.get(key, default)


# KIT_MODEL -> CHRONO_MODEL (chronomancer layer); KIT_MEM0_MODEL -> MEM0_MODEL (mem0-synthesis layer, independent).
def load_config():
    """Return (path, base_url, api_key, model, mem0_model) from environment. Stdlib os only."""
    path = os.getenv("KIT_PATH", "")
    base_url = os.getenv("KIT_BASE_URL", "http://localhost:8000")
    api_key = os.getenv("KIT_API_KEY", "")
    model = os.getenv("KIT_MODEL", "mock-chrono-model")
    mem0_model = os.getenv("KIT_MEM0_MODEL", "mock-mem0-model")
    return path, base_url, api_key, model, mem0_model


if _ENABLE:
    _missing = [v for v in ("KIT_PATH", "KIT_BASE_URL", "KIT_MODEL", "KIT_API_KEY") if not os.getenv(v)]
    if _missing:
        raise RuntimeError("KIT_LIVE=true but missing required env: " + ", ".join(_missing) + " — set them in kit-tests/.env.")

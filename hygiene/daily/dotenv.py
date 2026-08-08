import os

model_name = os.getenv("KIT_MODEL")
if os.getenv("KIT_ENABLE_REGISTRY_CLASHES", "false").lower() == "true" and not model_name:
    raise RuntimeError(
        "KIT_MODEL required when KIT_ENABLE_REGISTRY_CLASHES=true"
    )


def load_config():
    """Return (base_url, api_key, model) from environment. Stdlib os only; no new deps."""
    base_url = os.getenv("KIT_BASE_URL", "")
    api_key = os.getenv("KIT_API_KEY")
    model = os.getenv("KIT_MODEL")
    if os.getenv("KIT_ENABLE_REGISTRY_CLASHES", "false").lower() == "true" and not api_key:
        raise RuntimeError("KIT_API_KEY required when KIT_ENABLE_REGISTRY_CLASHES=true")
    return base_url, api_key, model

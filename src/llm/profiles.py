from pathlib import Path
import yaml
from typing import Dict, Optional

PROFILES_PATH = Path("config/profiles.yaml")

def load_profiles() -> Dict[str, dict]:
    if not PROFILES_PATH.exists():
        raise FileNotFoundError(f"Профили не найдены: {PROFILES_PATH}")
    with open(PROFILES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {p["id"]: p for p in data["profiles"]}

def get_profile(profile_id: str) -> Optional[dict]:
    profiles = load_profiles()
    return profiles.get(profile_id)
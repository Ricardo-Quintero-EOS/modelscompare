import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from tempfile import NamedTemporaryFile


@dataclass(slots=True)
class Preferences:
    favorite_models: list[str]
    providers: list[str]
    categories: list[str]
    tiers: list[str]
    release_statuses: list[str]
    thresholds: list[str]
    sort_by: str
    display_unit: str
    export_formats: list[str]
    setup_completed: bool

    @classmethod
    def defaults(cls) -> "Preferences":
        return cls(
            favorite_models=[],
            providers=[],
            categories=[],
            tiers=[],
            release_statuses=[],
            thresholds=[],
            sort_by="input",
            display_unit="usd",
            export_formats=["csv", "xlsx"],
            setup_completed=False,
        )


def default_preferences_path() -> Path:
    if os.name == "nt":
        config_root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        config_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_root / "modelscompare" / "config.json"


def _string_list(value: object, key: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"The '{key}' preference must be a list of strings.")
    unique: dict[str, str] = {}
    for item in value:
        unique.setdefault(item.casefold(), item)
    return list(unique.values())


def load_preferences(path: Path | None = None, legacy_path: Path | None = None) -> Preferences:
    config_path = path or default_preferences_path()
    if config_path.exists():
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("The preferences file must contain a JSON object.")
        preferences = Preferences.defaults()
        for field in fields(Preferences):
            if field.name not in raw:
                continue
            value = raw[field.name]
            if field.name in {
                "favorite_models", "providers", "categories", "tiers",
                "release_statuses", "thresholds", "export_formats",
            }:
                value = _string_list(value, field.name)
            elif field.name == "sort_by" and value not in {
                "name", "provider", "input", "cached_read", "cached_write", "output",
            }:
                raise ValueError("The saved sort option is not supported.")
            elif field.name == "display_unit" and value not in {"usd", "credits"}:
                raise ValueError("The saved display unit must be 'usd' or 'credits'.")
            elif field.name == "setup_completed" and not isinstance(value, bool):
                raise ValueError("The saved setup status must be a boolean.")
            setattr(preferences, field.name, value)
        return preferences

    old_path = legacy_path or config_path.with_name("selection.json")
    if old_path.exists():
        raw = json.loads(old_path.read_text(encoding="utf-8"))
        models = raw.get("models") if isinstance(raw, dict) else None
        favorites = _string_list(models, "models")
        migrated = Preferences.defaults()
        migrated.favorite_models = favorites
        migrated.setup_completed = True
        return migrated
    return Preferences.defaults()


def save_preferences(preferences: Preferences, path: Path | None = None) -> Path:
    config_path = path or default_preferences_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(preferences), ensure_ascii=False, indent=2) + "\n"
    with NamedTemporaryFile("w", encoding="utf-8", dir=config_path.parent, delete=False) as file:
        temporary_path = Path(file.name)
        file.write(payload)
    temporary_path.replace(config_path)
    return config_path

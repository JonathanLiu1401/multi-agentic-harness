"""Write clc /cost rates into the profile template, live settings, and .claude.json cache."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from clc_pricing import additional_model_costs, apply_settings_overrides, settings_overrides

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "claude-clc" / "settings.json"
LIVE = Path.home() / ".claude-clc" / "settings.json"
CACHE = Path.home() / ".claude-clc" / ".claude.json"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _patch_settings(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    apply_settings_overrides(data)
    _write_json(path, data)
    n = len((data.get("modelPricing") or {}).get("overrides") or {})
    print(f"settings overrides n={n} -> {path}")


def _patch_cache(path: Path) -> None:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"skip cache (invalid JSON): {path} ({exc})")
            return
        try:
            shutil.copy2(path, str(path) + ".bak")
        except OSError:
            pass
    else:
        data = {"hasCompletedOnboarding": True, "bypassPermissionsModeAccepted": True}
    if not isinstance(data, dict):
        print(f"skip cache (not an object): {path}")
        return
    cache = data.setdefault("additionalModelCostsCache", {})
    if not isinstance(cache, dict):
        cache = {}
        data["additionalModelCostsCache"] = cache
    cache.update(additional_model_costs())
    _write_json(path, data)
    print(f"cache ids n={len(additional_model_costs())} -> {path}")


def main() -> int:
    _patch_settings(TEMPLATE)
    if LIVE.is_file():
        _patch_settings(LIVE)
    else:
        print(f"skip live settings (missing): {LIVE}")
    _patch_cache(CACHE)
    missing = sorted(set(settings_overrides()) - set(json.loads(TEMPLATE.read_text(encoding="utf-8")).get("availableModels") or []))
    extra = sorted(set(json.loads(TEMPLATE.read_text(encoding="utf-8")).get("availableModels") or []) - set(settings_overrides()))
    if extra:
        print("FAIL picker ids without rates: " + ", ".join(extra))
        return 1
    if missing:
        print("note rates without picker rows: " + ", ".join(missing))
    print("ALL PRICING APPLIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

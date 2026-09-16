"""Refresh ~/.claude-clo/settings.json from the live OpenRouter catalog.

Fetches GET /api/v1/models?output_modalities=all (full catalog, not the
text-only default) and rewrites availableModels, modelPicker, and
modelPricing. Called by the clo launcher before starting Claude Code.
On fetch failure, leaves the previous picker in place.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

CATALOG_URL = (
    "https://openrouter.ai/api/v1/models?output_modalities=all&limit=1000"
)
PREFERRED_DEFAULTS = (
    "~anthropic/claude-sonnet-latest",
    "anthropic/claude-sonnet-5",
    "anthropic/claude-sonnet-4.6",
    "anthropic/claude-sonnet-4.5",
)
KEY_FILE = Path.home() / ".cc-bridge" / "secrets" / "openrouter-api.key"
LIVE_SETTINGS = Path.home() / ".claude-clo" / "settings.json"
LIVE_CACHE = Path.home() / ".claude-clo" / ".claude.json"
TEMPLATE = (
    Path(__file__).resolve().parents[1] / "templates" / "claude-clo" / "settings.json"
)


def _read_key() -> str:
    if KEY_FILE.is_file():
        return KEY_FILE.read_text(encoding="utf-8").strip()
    return (os.environ.get("OPENROUTER_API_KEY") or "").strip()


def _get(url: str, key: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + key,
            "User-Agent": "clo-refresh",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_catalog(key: str) -> list[dict]:
    rows: list[dict] = []
    url: str | None = CATALOG_URL
    seen = set()
    while url:
        payload = _get(url, key)
        chunk = payload.get("data") or []
        for item in chunk:
            mid = item.get("id")
            if not mid or mid in seen:
                continue
            seen.add(mid)
            rows.append(item)
        nxt = (payload.get("links") or {}).get("next")
        url = nxt if nxt and nxt not in seen else None
        if len(rows) >= 5000:
            break
    return rows


def _f(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mtok(per_token: float | None) -> float:
    if per_token is None:
        return 0.0
    usd = round(per_token * 1_000_000.0, 4)
    if usd != usd:
        return 0.0
    # Claude Code rejects rows outside 0..10000 USD/MTok (STT models and
    # OpenRouter routers that send -1 sentinels).
    if usd < 0.0:
        return 0.0
    if usd > 10000.0:
        return 10000.0
    return usd


def _ctx(model: dict) -> int:
    top = model.get("top_provider") or {}
    for src in (model.get("context_length"), top.get("context_length")):
        try:
            n = int(src)
            if n > 0:
                return n
        except (TypeError, ValueError):
            pass
    return 0


def _picker_id(mid: str, ctx: int) -> str:
    if ctx >= 1_000_000 and not mid.endswith("[1m]"):
        return mid + "[1m]"
    return mid


def _behaves_as(mid: str, name: str) -> str:
    s = (mid + " " + name).lower()
    if "fable" in s:
        return "claude-fable-5"
    if "opus" in s:
        return "claude-opus-5"
    if "haiku" in s:
        return "claude-haiku-4-5"
    return "claude-sonnet-5"


def _modalities(model: dict) -> str:
    arch = model.get("architecture") or {}
    outs = arch.get("output_modalities") or arch.get("modality") or []
    if isinstance(outs, str):
        outs = [outs]
    outs = [str(x) for x in outs if x]
    if not outs or outs == ["text"]:
        return "text"
    return "+".join(outs)


def _price_row(model: dict) -> dict:
    pricing = model.get("pricing") or {}
    inp = _mtok(_f(pricing.get("prompt")))
    out = _mtok(_f(pricing.get("completion")))
    cr = _mtok(_f(pricing.get("input_cache_read") or pricing.get("cached")))
    cw_raw = _f(pricing.get("input_cache_write"))
    cw = _mtok(cw_raw) if cw_raw is not None else inp
    return {
        "input": inp,
        "output": out,
        "cacheRead": cr,
        "cacheWrite": cw,
    }


def build_picker(catalog: list[dict]) -> tuple[list[str], list[dict], dict, dict]:
    available: list[str] = []
    options: list[dict] = []
    overrides: dict[str, dict] = {}
    costs: dict[str, dict] = {}
    seen_ids: set[str] = set()

    for model in catalog:
        mid = (model.get("id") or "").strip()
        if not mid or mid in seen_ids:
            continue
        seen_ids.add(mid)
        ctx = _ctx(model)
        pid = _picker_id(mid, ctx)
        name = (model.get("name") or mid).strip()
        mods = _modalities(model)
        ctx_label = f"{ctx // 1000}k ctx" if ctx else "ctx unknown"
        desc = f"{name} via OpenRouter - {ctx_label}"
        if mods != "text":
            desc += f" ({mods})"
        available.append(pid)
        options.append(
            {
                "model": pid,
                "label": name,
                "description": desc,
                "behavesAs": _behaves_as(mid, name),
            }
        )
        row = _price_row(model)
        overrides[pid] = row
        if pid != mid:
            overrides[mid] = row
        cost = {
            "inputTokens": row["input"],
            "outputTokens": row["output"],
            "promptCacheWriteTokens": row["cacheWrite"],
            "promptCacheReadTokens": row["cacheRead"],
            "webSearchRequests": 0.01,
        }
        costs[pid] = cost
        if pid != mid:
            costs[mid] = cost
    return available, options, overrides, costs


def _pick_default(available: list[str], previous: str | None) -> str:
    ids = set(available)
    bare = {i.replace("[1m]", ""): i for i in available}
    if previous:
        if previous in ids:
            return previous
        b = previous.replace("[1m]", "")
        if b in bare:
            return bare[b]
    for pref in PREFERRED_DEFAULTS:
        if pref in ids:
            return pref
        if pref in bare:
            return bare[pref]
        for aid in available:
            if aid.replace("[1m]", "").startswith(pref):
                return aid
    return available[0] if available else "~anthropic/claude-sonnet-latest[1m]"


def _load_settings() -> dict:
    for path in (LIVE_SETTINGS, TEMPLATE):
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return data
    return {
        "effortLevel": "high",
        "skipDangerousModePermissionPrompt": True,
        "theme": "dark",
        "env": {
            "ENABLE_TOOL_SEARCH": "auto:9999",
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "8192",
        },
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def apply(settings: dict, available: list[str], options: list[dict],
          overrides: dict, default: str) -> dict:
    settings["model"] = default
    settings["availableModels"] = available
    settings["enforceAvailableModels"] = True
    picker = settings.get("modelPicker")
    if not isinstance(picker, dict):
        picker = {}
    picker["options"] = options
    picker["replaceBuiltInOptions"] = True
    settings["modelPicker"] = picker
    pricing = settings.get("modelPricing")
    if not isinstance(pricing, dict):
        pricing = {}
    pricing["overrides"] = overrides
    settings["modelPricing"] = pricing
    env = settings.get("env")
    if not isinstance(env, dict):
        env = {}
    env["ENABLE_TOOL_SEARCH"] = "auto:9999"
    env.setdefault("CLAUDE_CODE_MAX_OUTPUT_TOKENS", "8192")
    settings["env"] = env
    return settings


def apply_cost_cache(costs: dict) -> None:
    if LIVE_CACHE.is_file():
        try:
            data = json.loads(LIVE_CACHE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        if not isinstance(data, dict):
            return
    else:
        data = {
            "hasCompletedOnboarding": True,
            "bypassPermissionsModeAccepted": True,
        }
    cache = data.setdefault("additionalModelCostsCache", {})
    if not isinstance(cache, dict):
        cache = {}
        data["additionalModelCostsCache"] = cache
    cache.update(costs)
    _write_json(LIVE_CACHE, data)


def main() -> int:
    key = _read_key()
    if not key:
        print("clo: no OpenRouter key; skip catalog refresh", file=sys.stderr)
        return 0
    try:
        catalog = fetch_catalog(key)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"clo: catalog refresh failed ({exc.__class__.__name__}); using previous picker", file=sys.stderr)
        return 0
    if not catalog:
        print("clo: empty OpenRouter catalog; using previous picker", file=sys.stderr)
        return 0
    available, options, overrides, costs = build_picker(catalog)
    settings = _load_settings()
    previous = settings.get("model") if isinstance(settings.get("model"), str) else None
    default = _pick_default(available, previous)
    apply(settings, available, options, overrides, default)
    _write_json(LIVE_SETTINGS, settings)
    apply_cost_cache(costs)
    print(f"clo: refreshed {len(available)} OpenRouter models (default {default})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

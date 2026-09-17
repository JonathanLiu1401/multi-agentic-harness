"""Refresh ~/.claude-clo/settings.json from the live OpenRouter catalog.

Fetches GET /api/v1/models?output_modalities=all&sort=most-popular
(full catalog, ranked like https://openrouter.ai/models popularity)
and rewrites availableModels, modelPicker, and modelPricing. Called by
the clo launcher before starting Claude Code. On fetch failure, leaves
the previous picker in place.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

CATALOG_URL = (
    "https://openrouter.ai/api/v1/models"
    "?output_modalities=all&limit=1000&sort=most-popular"
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
    # Claude Code assumes 200k unless the id ends in [1m]. Pin every row to
    # 1M so 1M OpenRouter models are not clipped. Native size goes in the
    # description; OpenRouter strips [1m] before routing.
    if mid.endswith("[1m]"):
        return mid
    return mid + "[1m]"


def _ctx_label(ctx: int) -> str:
    if ctx >= 1_000_000:
        m = ctx / 1_000_000
        if abs(m - round(m)) < 0.05:
            return f"{int(round(m))}M native"
        return f"{m:.1f}M native"
    if ctx >= 1000:
        return f"{ctx // 1000}k native"
    if ctx > 0:
        return f"{ctx} native"
    return "native ctx unknown"


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
        desc = f"{name} via OpenRouter - {_ctx_label(ctx)} (TUI 1M)"
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
    options.sort(key=lambda o: (_company(o["model"]), (o.get("label") or "").lower()))
    available = [o["model"] for o in options]
    return available, options, overrides, costs


def _company(mid: str) -> str:
    bare = mid.replace("[1m]", "").lstrip("~")
    return bare.split("/", 1)[0].lower() if "/" in bare else bare.lower()


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
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "8192",
            "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
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
    settings["autoCompactWindow"] = 1000000
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
    env.pop("ENABLE_TOOL_SEARCH", None)
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "8192"
    env["CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS"] = "1"
    settings["env"] = env
    settings["disabledBuiltinTools"] = ["WebSearch"]
    perms = settings.setdefault("permissions", {})
    if isinstance(perms, dict):
        allow = perms.setdefault("allow", [])
        if isinstance(allow, list):
            for t in ["mcp__duckduckgo__duckduckgo_search", "mcp__duckduckgo__web_search"]:
                if t not in allow:
                    allow.append(t)
    _ensure_or_hook(settings)
    _ensure_duckduckgo_mcp(settings)
    return settings


def _ensure_duckduckgo_mcp(settings: dict) -> None:
    server_py = Path.home() / ".cc-bridge" / "ddg_search_server.py"
    cmd = "py" if sys.platform == "win32" else "python3"
    args = ["-3", str(server_py)] if sys.platform == "win32" else [str(server_py)]
    entry = {"command": cmd, "args": args}

    clo_claude_json = Path.home() / ".claude-clo" / ".claude.json"
    if clo_claude_json.is_file():
        try:
            data = json.loads(clo_claude_json.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}

    mcp_servers = data.setdefault("mcpServers", {})
    if not isinstance(mcp_servers, dict):
        mcp_servers = {}
        data["mcpServers"] = mcp_servers
    mcp_servers["duckduckgo"] = entry
    _write_json(clo_claude_json, data)

    settings_mcp = settings.setdefault("mcpServers", {})
    if isinstance(settings_mcp, dict):
        settings_mcp["duckduckgo"] = entry


def _ensure_or_hook(settings: dict) -> None:
    hook_py = Path.home() / ".cc-bridge" / "clo_or_hook.py"
    cmd = f'py -3 "{hook_py}"'
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
    entries = hooks.get("UserPromptSubmit")
    if not isinstance(entries, list):
        entries = []
    kept = []
    for entry in entries:
        blob = json.dumps(entry)
        if "clo_or_hook.py" in blob or "/or" in blob:
            continue
        kept.append(entry)
    kept.append(
        {
            "hooks": [
                {
                    "type": "command",
                    "command": cmd,
                    "timeout": 30,
                    "statusMessage": "Searching OpenRouter catalog",
                }
            ]
        }
    )
    hooks["UserPromptSubmit"] = kept
    settings["hooks"] = hooks


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


def search_catalog(query: str, catalog: list[dict]) -> list[dict]:
    q = " ".join(query.lower().split())
    if not q:
        return []
    terms = q.split()
    hits: list[dict] = []
    for model in catalog:
        blob = " ".join(
            str(model.get(k) or "")
            for k in ("id", "name", "description", "canonical_slug")
        ).lower()
        if all(t in blob for t in terms):
            hits.append(model)
    return hits


def print_search(query: str, catalog: list[dict]) -> int:
    hits = search_catalog(query, catalog)
    if not hits:
        print(f"clo: no OpenRouter models matching {query!r}")
        return 0
    print(f"clo: {len(hits)} match(es) for {query!r} (popularity order)")
    print("Use /model then paste the id. In the picker, press / to type-filter.")
    for i, model in enumerate(hits[:25], 1):
        ctx = _ctx(model)
        pid = _picker_id(model.get("id") or "", ctx)
        name = (model.get("name") or pid).strip()
        print(f"  {i:2d}. {name}")
        print(f"      {pid}  ({_ctx_label(ctx)})")
    if len(hits) > 25:
        print(f"  ... {len(hits) - 25} more. Narrow the query.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    search_q = None
    if args and args[0] in ("--search", "-s"):
        search_q = " ".join(args[1:]).strip()
        if not search_q:
            print("clo: usage: refresh_clo_models.py --search <query>", file=sys.stderr)
            return 2
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
    if search_q is not None:
        return print_search(search_q, catalog)
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

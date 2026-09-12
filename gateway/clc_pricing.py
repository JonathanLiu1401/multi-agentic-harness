"""Canonical /cost rates for clc picker IDs. USD per million tokens.

Cursor-hosted Grok/Composer use Cursor's published card (Fast is 2x-6x).
Everything else uses the underlying provider list (Sept 2026). Cursor
dashboard "Included" will not match these dollars.

Sources:
  https://cursor.com/docs/models
  https://platform.claude.com/docs/en/about-claude/pricing
  https://developers.openai.com/api/docs/pricing
  https://ai.google.dev/pricing
  https://docs.x.ai/developers/pricing
  https://docs.z.ai/guides/overview/pricing
"""
from __future__ import annotations

from typing import Any

# (input, output, cacheRead, cacheWrite)
RATES: dict[str, tuple[float, float, float, float]] = {
    # Cursor first-party (cursor.com/docs/models). Auto bills the routed model;
    # default uses Grok 4.6 standard as the estimate.
    "default": (2.0, 6.0, 0.5, 2.0),
    "grok-4.6": (2.0, 6.0, 0.5, 2.0),
    "grok-4.6-fast": (4.0, 12.0, 1.0, 4.0),
    "grok-4.5": (2.0, 6.0, 0.5, 2.0),
    "grok-4.5-fast": (4.0, 18.0, 1.0, 4.0),
    "composer-2.5": (0.5, 2.5, 0.2, 0.5),
    "composer-2.5-fast": (3.0, 15.0, 0.5, 3.0),
    # Anthropic (platform.claude.com/docs/en/about-claude/pricing).
    # Opus 5 / 4.8 Fast is Anthropic Fast mode ($10/$50), not the retired $15/$75 Opus 4.1 card.
    "claude-fable-5-1": (10.0, 50.0, 0.25, 12.50),
    "claude-fable-5": (10.0, 50.0, 1.0, 12.50),
    "claude-opus-5": (5.0, 25.0, 0.50, 6.25),
    "claude-opus-5-fast": (10.0, 50.0, 1.0, 12.50),
    "claude-opus-4-8": (5.0, 25.0, 0.50, 6.25),
    "claude-opus-4-8-fast": (10.0, 50.0, 1.0, 12.50),
    "claude-opus-4-7": (5.0, 25.0, 0.50, 6.25),
    "claude-opus-4-7-fast": (5.0, 25.0, 0.50, 6.25),
    "claude-opus-4-6": (5.0, 25.0, 0.50, 6.25),
    "claude-opus-4-5": (5.0, 25.0, 0.50, 6.25),
    "claude-sonnet-5": (2.0, 10.0, 0.20, 2.50),
    "claude-sonnet-4-6": (3.0, 15.0, 0.30, 3.75),
    "claude-sonnet-4-5": (3.0, 15.0, 0.30, 3.75),
    "claude-sonnet-4": (3.0, 15.0, 0.30, 3.75),
    "claude-haiku-4-5": (1.0, 5.0, 0.10, 1.25),
    # OpenAI (developers.openai.com/api/docs/pricing). Sol promo through 2026-11-21.
    # Fast = OpenAI Fast/priority (5.6 family 2x, GPT-5.5 2.5x).
    "gpt-5.6-sol": (4.0, 20.0, 0.40, 5.0),
    "gpt-5.6-sol-fast": (8.0, 40.0, 0.80, 10.0),
    "gpt-5.6-terra": (2.0, 12.0, 0.20, 2.50),
    "gpt-5.6-terra-fast": (4.0, 24.0, 0.40, 5.0),
    "gpt-5.6-luna": (0.20, 1.20, 0.02, 0.25),
    "gpt-5.6-luna-fast": (0.40, 2.40, 0.04, 0.50),
    "gpt-5.5": (5.0, 30.0, 0.50, 5.0),
    "gpt-5.5-fast": (12.50, 75.0, 1.25, 12.50),
    "gpt-5.4": (2.50, 15.0, 0.25, 2.50),
    "gpt-5.4-fast": (5.0, 30.0, 0.50, 5.0),
    "gpt-5.4-mini": (0.75, 4.50, 0.075, 0.75),
    "gpt-5.4-nano": (0.20, 1.25, 0.02, 0.20),
    "gpt-5.3-codex": (1.75, 14.0, 0.175, 1.75),
    "gpt-5.3-codex-fast": (3.50, 28.0, 0.35, 3.50),
    "gpt-5.2": (1.75, 14.0, 0.175, 1.75),
    "gpt-5.2-fast": (3.50, 28.0, 0.35, 3.50),
    "gpt-5.1": (1.25, 10.0, 0.125, 1.25),
    "gpt-5-mini": (0.25, 2.0, 0.025, 0.25),
    # Google (ai.google.dev/pricing). Flash 3.6-3.8 promo through 2026-12-31.
    "gemini-3.8-flash": (0.75, 3.75, 0.075, 0.75),
    "gemini-3.7-flash": (0.75, 3.75, 0.075, 0.75),
    "gemini-3.6-flash": (0.75, 3.75, 0.075, 0.75),
    "gemini-3.5-flash": (1.50, 9.0, 0.15, 1.50),
    "gemini-3-flash": (0.50, 3.0, 0.05, 0.50),
    "gemini-3.1-pro": (2.0, 12.0, 0.20, 2.0),
    "gemini-2.5-flash": (0.30, 2.50, 0.03, 0.30),
    # Meta Muse via Cursor docs.
    "muse-spark-1.3": (1.25, 4.25, 0.15, 1.25),
    # Moonshot / Z.ai list.
    "kimi-k3": (3.0, 15.0, 0.30, 3.0),
    "kimi-k2.7-code": (0.95, 4.0, 0.19, 0.95),
    "glm-5.2": (1.40, 4.40, 0.26, 1.40),
}


def override(inp: float, out: float, cache_read: float, cache_write: float) -> dict[str, float]:
    return {
        "input": inp,
        "output": out,
        "cacheRead": cache_read,
        "cacheWrite": cache_write,
    }


def settings_overrides() -> dict[str, dict[str, float]]:
    return {mid: override(*vals) for mid, vals in RATES.items()}


def cache_entry(inp: float, out: float, cache_read: float, cache_write: float) -> dict[str, float]:
    return {
        "inputTokens": inp,
        "outputTokens": out,
        "promptCacheWriteTokens": cache_write,
        "promptCacheReadTokens": cache_read,
        "webSearchRequests": 0.01,
    }


def additional_model_costs() -> dict[str, dict[str, float]]:
    return {mid: cache_entry(*vals) for mid, vals in RATES.items()}


def apply_settings_overrides(data: dict[str, Any]) -> None:
    pricing = data.setdefault("modelPricing", {})
    if not isinstance(pricing, dict):
        pricing = {}
        data["modelPricing"] = pricing
    pricing["overrides"] = settings_overrides()

"""Application settings loaded from environment variables and .env file."""

import logging
from typing import Annotated

from pydantic import AfterValidator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalise_log_level(value: str) -> str:
    normalised = value.upper()
    if normalised not in logging.getLevelNamesMapping():
        valid = list(logging.getLevelNamesMapping())
        raise ValueError(f"Invalid log_level {value!r}; expected one of {valid}")
    return normalised


class AppSettings(BaseSettings):
    """Application settings loaded from environment / .env file.

    Example:
        settings = AppSettings()
        print(settings.openai_api_key)
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str
    openai_base_url: str = "https://opencode.ai/zen/go/v1"
    language_model_name: str = "openai/glm-5"
    format_model_name: str = "openai/glm-5"
    language_model_temperature: float = 0.0
    duckdb_path: str = "./dev_data/datastudio.duckdb"
    log_level: Annotated[str, AfterValidator(_normalise_log_level)] = "INFO"
    # Identity for unauthenticated callers until a real IdP (MSAL/OIDC) is wired.
    # Every request without an Authorization token resolves to this single guest user.
    guest_user_id: str = "guest"
    guest_display_name: str = "Guest"
    # Token pricing (USD per million tokens) used to compute eval cost_usd.
    input_token_price_per_million: float = 0.0
    output_token_price_per_million: float = 0.0
    # Eval SLOs — the budget gate fails when a run regresses past these.
    eval_min_pass_rate: float = 0.8
    # How many times each case runs. >1 turns a noisy single pass/fail into a per-case
    # consistency (pass@k) rate, so a flaky 55% case is distinguishable from a reliable 95%
    # one. Kept at 1 by default (fast); raise it for an assertive run (e.g. 5).
    eval_repeats: int = 1
    # A case must pass at least this fraction of its repeated attempts to clear the gate.
    eval_min_consistency: float = 0.8
    eval_max_p95_latency_s: float = 180.0
    eval_max_avg_output_tokens: float = 3000.0
    # Guards against conversation-memory bloat: injected history lands in input tokens,
    # so a runaway window (or double-injected turns) trips this before it hits cost. The
    # scenario track (multi-widget executive dashboards, drilldown follow-up chains, and
    # per-widget SQL context in the narrative prompt) lifted full runs to ~4.4k/case; the
    # ceiling keeps ~35% headroom over that.
    eval_max_avg_input_tokens: float = 6000.0
    # Cases run through a bounded thread pool; the ceiling is LLM rate limits.
    eval_max_workers: int = 4
    # Per-question wall-clock ceiling in the CLI; None disables it in the eval runner.
    query_timeout_s: float = 120.0

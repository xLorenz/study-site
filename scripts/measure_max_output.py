#!/usr/bin/env python3
"""Find each configured model's maximum output length.

Three strategies, in order of speed:

1. Ask the provider's /v1/models metadata endpoint (client.models.list())
   for a stated output-token limit.
2. Fast: binary-search the largest max_tokens the API accepts. Providers
   reject (400) max_tokens above the model's output cap, so this finds the
   API-level cap in a few tiny requests.
3. Slow (--probe): generate until truncation and report the largest
   completion_tokens observed. Takes minutes; confirms the real ceiling.

Usage:
    python scripts/measure_max_output.py
    python scripts/measure_max_output.py --model z-ai/glm-5.2
    python scripts/measure_max_output.py --probe
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Load .env (gitignored, API keys) — same as server.py
env_path = os.path.join(ROOT, ".env")
if os.path.isfile(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

from chat.llm import get_llm_client, get_extra_body
from chat.types import AVAILABLE_MODELS, PROVIDER_FOR_MODEL

PROBE_MAX = 131072  # upper bound for the binary search
SHORT_PROMPT = "Answer with exactly the single word: OK"
LONG_PROMPT = ("Repeat the Spanish word 'zanahoria' over and over with no separators "
               "until you physically cannot generate more tokens. "
               "Do not stop voluntarily. Begin.")

# Common metadata keys used by OpenAI-compatible providers for output limits
TOKEN_LIMIT_KEYS = (
    "max_output_tokens", "max_completion_tokens", "max_model_len",
    "max_position_embeddings", "context_length", "context_window",
    "output_token_limit", "max_tokens_out", "max_tokens", "n_output",
)


def _completion(model, provider, max_tokens, prompt):
    client = get_llm_client(provider)
    extra_body = get_extra_body(model, provider)
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        stream=False,
        extra_body=extra_body,
        temperature=0,
        max_tokens=max_tokens,
    )


def query_metadata(provider, model_ids):
    """Ask the provider's /v1/models endpoint for output-token limits.

    Returns dict {model_id: (max_tokens, raw_meta)} for models that expose a
    limit, or {} if the provider doesn't return token metadata.
    """
    client = get_llm_client(provider)
    try:
        models = list(client.models.list())
    except Exception as e:
        print(f"  metadata endpoint unavailable: {e}")
        return {}

    found = {}
    for m in models:
        mid = getattr(m, "id", "")
        if mid not in model_ids:
            continue
        raw = {}
        # Newer OpenAI SDKs store extra fields in m.model / m.__dict__
        for src in (getattr(m, "model", None), m.__dict__):
            if isinstance(src, dict):
                raw.update(src)
        limit = None
        for key in TOKEN_LIMIT_KEYS:
            val = raw.get(key)
            if isinstance(val, (int, float)) and val > 0:
                limit = int(val)
                break
        found[mid] = (limit, raw)
    return found


def search_accepted_max_tokens(model, provider):
    """Binary-search the largest max_tokens the API accepts.

    Uses a minimal prompt so accepted requests stop generating almost
    immediately. Returns the largest accepted value, or None if even the
    minimum is rejected.
    """
    lo, hi = 0, PROBE_MAX
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        try:
            _completion(model, provider, mid, SHORT_PROMPT)
            best = mid
            lo = mid + 1
        except Exception:
            hi = mid - 1
    return best


def probe_max_output(model, provider, max_tokens, repeats=3):
    """Generate until truncation to confirm the real ceiling (slow)."""
    best = 0
    last_finish = None
    saw_reasoning = False
    for i in range(repeats):
        resp = _completion(model, provider, max_tokens, LONG_PROMPT)
        usage = resp.usage
        n = usage.completion_tokens if usage else -1
        finish = resp.choices[0].finish_reason
        msg = resp.choices[0].message
        reasoning = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None)
        if reasoning:
            saw_reasoning = True
        print(
            f"  [{i + 1}/{repeats}] completion_tokens={n} finish={finish}"
            + (" (reasoning present)" if reasoning else "")
        )
        if n > best:
            best = n
        last_finish = finish

    note = "capped (finish=length)" if last_finish == "length" else f"stopped early (finish={last_finish})"
    return best, note, saw_reasoning


def main():
    parser = argparse.ArgumentParser(description="Find each model's max output length.")
    parser.add_argument("--model", help="Only probe this model (default: all AVAILABLE_MODELS)")
    parser.add_argument("--probe", action="store_true",
                        help="Also generate until truncation (slow, minutes) to confirm the cap")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    models = [args.model] if args.model else AVAILABLE_MODELS
    providers = sorted({PROVIDER_FOR_MODEL.get(m, "nvidia") for m in models})

    # 1. Try the provider metadata endpoint first
    print("Querying provider metadata endpoints...")
    meta = {}
    for provider in providers:
        meta.update(query_metadata(provider, set(models)))

    for model in models:
        provider = PROVIDER_FOR_MODEL.get(model, "nvidia")
        print(f"\n=== {model} ({provider}) ===")
        limit, raw = meta.get(model, (None, None))
        if limit:
            print(f"  PROVIDER-STATED MAX OUTPUT: {limit} tokens")
            print(f"  metadata: {raw}")
            continue
        if raw is not None:
            print(f"  metadata returned, but no token limit key found: {raw}")

        # 2. Fast: largest accepted max_tokens
        print("  searching largest accepted max_tokens...")
        cap = search_accepted_max_tokens(model, provider)
        if cap is None:
            print("  FAILED: even max_tokens=1 is rejected")
            continue
        print(f"  API-LEVEL MAX OUTPUT: {cap} tokens (largest accepted max_tokens)")

        # 3. Optional slow confirmation
        if args.probe:
            print(f"  confirming by generation (up to {cap} tokens, this takes a while)...")
            best, note, reasoning = probe_max_output(model, provider, cap, args.repeats)
            extra = " (includes reasoning tokens)" if reasoning else ""
            print(f"  MEASURED MAX OUTPUT: ~{best} tokens — {note}{extra}")


if __name__ == "__main__":
    main()

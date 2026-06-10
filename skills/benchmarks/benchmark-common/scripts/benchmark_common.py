#!/usr/bin/env python3
"""Common utilities for Hermes model benchmarks.
No third-party dependencies. OpenAI-compatible /v1/chat/completions endpoints.
"""
from __future__ import annotations
import argparse, dataclasses, datetime as dt, hashlib, json, os, re, sqlite3, subprocess, time, urllib.error, urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_VERSION = "0.2.0"
PROVIDER_DEFAULTS = {
    "omniroute": ("${OMNIROUTE_URL}/v1", "OMNIROUTE_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "nous": ("https://inference-api.nousresearch.com/v1", "NOUS_API_KEY"),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "xai": ("https://api.x.ai/v1", "XAI_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "cerebras": ("https://api.cerebras.ai/v1", "CEREBRAS_API_KEY"),
}

# ─── Data Classes ──────────────────────────────────────────────────────

@dataclasses.dataclass
class Target:
    provider: str
    model: str
    base_url: str
    api_key: str

@dataclasses.dataclass
class CaseResult:
    case_id: str
    category: str
    prompt: str
    expected: str
    response: str
    passed: bool
    score: float
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    cost_estimated: bool = True
    error: str = ""
    notes: str = ""
    raw_json: str = ""

# ─── Timing / IDs ──────────────────────────────────────────────────────

def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def make_run_id(benchmark_name: str, model: str) -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = hashlib.sha1(f"{benchmark_name}:{model}:{stamp}:{time.time_ns()}".encode()).hexdigest()[:8]
    return f"{benchmark_name}-{stamp}-{suffix}"

# ─── Environment / Secrets ─────────────────────────────────────────────

def load_dotenv() -> None:
    """Load ~/.hermes/.env into os.environ (idempotent, does not overwrite)."""
    env_path = Path.home() / ".hermes" / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, value = s.split("=", 1)
        key = key.replace("export ", "").strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

def load_dotenv_key(name: str) -> str:
    """Return a specific env var, falling back to ~/.hermes/.env lookup."""
    if os.environ.get(name):
        return os.environ[name]
    env_path = Path.home() / ".hermes" / ".env"
    if env_path.exists():
        for line in env_path.read_text(errors="replace").splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == name:
                return v.strip().strip('"').strip("'")
    return ""

def read_op_secret(ref: str) -> str | None:
    """Read a 1Password secret via `op read` (best-effort, returns None on failure)."""
    try:
        out = subprocess.check_output(
            ["op", "read", ref], text=True, stderr=subprocess.DEVNULL, timeout=15
        ).strip()
        return out or None
    except Exception:
        return None

def omniroute_hermes_key() -> str | None:
    """Retrieve the OmniRoute Hermes API key from its SQLite storage."""
    db = Path.home() / "OmniRoute" / "data" / "storage.sqlite"
    if not db.exists():
        return None
    try:
        con = sqlite3.connect(str(db))
        row = con.execute(
            "SELECT key FROM api_keys WHERE name='Hermes' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        con.close()
        return row[0] if row else None
    except Exception:
        return None

def _config_provider(provider: str) -> dict[str, Any]:
    """Read a provider block from ~/.hermes/config.yaml (best-effort)."""
    cfg = Path.home() / ".hermes" / "config.yaml"
    if not cfg.exists():
        return {}
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(cfg.read_text()) or {}
        return (data.get("providers") or {}).get(provider) or {}
    except Exception:
        return {}

# ─── Provider Resolution ───────────────────────────────────────────────

def resolve_target(
    provider: str,
    model: str,
    base_url: str | None = None,
    api_key: str | None = None,
) -> Target:
    """
    Resolve provider, model, base_url, and api_key into a Target.
    Supports: CLI flags, env vars, config.yaml, 1Password, OmniRoute SQLite.
    """
    load_dotenv()
    provider = provider or "openrouter"
    cfg = _config_provider(provider)
    default_base, env_name = PROVIDER_DEFAULTS.get(provider, (base_url or "", ""))
    resolved_base = (base_url or cfg.get("base_url") or default_base).rstrip("/")

    if api_key:
        resolved_key = api_key
    else:
        configured = cfg.get("api_key") or ""
        if configured.startswith("${") and configured.endswith("}"):
            resolved_key = os.environ.get(configured[2:-1], "")
        elif configured:
            resolved_key = configured
        else:
            candidates = [
                f"{provider.upper()}_API_KEY",
                f"{provider.upper().replace('-', '_')}_API_KEY",
            ]
            if provider == "openrouter":
                candidates += ["OPENROUTER_ENRICH_KEY"]
            if provider == "nous":
                candidates += ["NOUS_API_KEY"]
            resolved_key = next(
                (os.environ.get(k, "") for k in candidates if os.environ.get(k)), ""
            )
            if provider == "openrouter" and not resolved_key:
                resolved_key = read_op_secret(
                    "op://Ambler-Tokens/OpenRouter/api_key_enrich"
                ) or ""
            if provider == "omniroute" and not resolved_key:
                resolved_key = omniroute_hermes_key() or ""
            if provider == "nous" and not resolved_key:
                resolved_key = read_op_secret(
                    "op://Ambler-Tokens/Nous/api_key"
                ) or ""

    if not resolved_base:
        raise RuntimeError(f"No base URL for provider {provider}; pass --base-url")
    if not resolved_key:
        raise RuntimeError(
            f"No API key for provider {provider}; pass --api-key or set env var"
        )
    return Target(provider, model, resolved_base, resolved_key)

def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", default="omniroute")
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url")
    parser.add_argument("--api-key")
    parser.add_argument("--db", default="results/benchmark.db")
    parser.add_argument("--obsidian-dir")
    parser.add_argument("--suite-version", default="v1")
    parser.add_argument("--benchmark-version", default="0.2.0")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--max-retries", type=int, default=0)
    parser.add_argument("--notes", default="")

# ─── JSON / Fence Utilities ─────────────────────────────────────────────

def strip_json_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) wrapping JSON content."""
    t = text.strip()
    if t.startswith("```"):
        m = re.search(r"```(?:json)?\s*(.*?)\s*```", t, re.S | re.I)
        if m:
            return m.group(1).strip()
    return t

def parse_json_loose(text: str) -> Any:
    """Parse JSON, stripping fences and falling back to first {...} match."""
    clean = strip_json_fences(text.strip())
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise

def classify_error(exc: Exception | str) -> str:
    """Classify an API error into a standard category."""
    text = str(exc).lower()
    if "401" in text or "403" in text or "auth" in text or "api key" in text:
        return "auth_error"
    if "429" in text or "rate limit" in text:
        return "rate_limited"
    if "404" in text or "not found" in text:
        return "model_not_found"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    return "api_error"

# ─── API Call ───────────────────────────────────────────────────────────

def chat_completion_raw(
    target: Target,
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.0,
    max_tokens: int = 512,
    timeout: int = 60,
    extra: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], int]:
    """
    Low-level chat completion. Returns (response_dict, latency_ms).
    Supports optional `extra` payload fields (e.g. reasoning, seed).
    """
    payload: Dict[str, Any] = {
        "model": target.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if extra:
        payload.update(extra)
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if target.api_key:
        headers["Authorization"] = f"Bearer {target.api_key}"
    req = urllib.request.Request(
        f"{target.base_url}/chat/completions",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace")), int(
                (time.perf_counter() - start) * 1000
            )
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:1000]}") from e

def chat_completion(
    target: Target,
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.0,
    max_tokens: int = 512,
    timeout: int = 60,
    extra: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Dict[str, int], int]:
    """
    Chat completion returning (text, usage_dict, latency_ms).
    Handles models that return reasoning instead of content.
    """
    resp, latency_ms = chat_completion_raw(
        target, messages,
        temperature=temperature, max_tokens=max_tokens,
        timeout=timeout, extra=extra,
    )
    text, usage = extract_text_and_usage(resp)
    return text, usage, latency_ms

def extract_text_and_usage(resp: Dict[str, Any]) -> Tuple[str, Dict[str, int]]:
    """Extract response text and normalized usage from an API response."""
    choices = resp.get("choices") or [{}]
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if content is None or content == "":
        content = msg.get("reasoning") or ""
    usage = resp.get("usage") or {}
    actual_model = resp.get("model") or ""
    prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens) or 0)
    cost = float(usage.get("cost") or 0)
    return content, {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "actual_model": actual_model,
        # Preserve both names: token_cost_from_pricing historically reads
        # ``cost`` while DB/reporting fields use ``cost_usd``.
        "cost": cost,
        "cost_usd": cost,
        "cost_details": usage.get("cost_details") or {},
    }

# ─── Pricing / Cost ────────────────────────────────────────────────────

def canonical_model_id(model: str) -> str:
    """Strip provider prefix from model IDs (e.g. 'omniroute:google/gemini-3.1-pro' → 'google/gemini-3.1-pro')."""
    m = model.strip()
    for prefix in ("omniroute:", "openrouter:", "nous:", "groq/"):
        if m.startswith(prefix):
            m = m[len(prefix):]
    return m

def fetch_openrouter_pricing() -> dict[str, tuple[Decimal, Decimal]]:
    """Fetch live pricing from OpenRouter /models endpoint (dollars per token)."""
    key = load_dotenv_key("OPENROUTER_API_KEY")
    headers: Dict[str, str] = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/models", headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace")).get(
                "data", []
            )
    except Exception:
        return {}
    out: dict[str, tuple[Decimal, Decimal]] = {}
    for item in data:
        mid = item.get("id")
        pricing = item.get("pricing") or {}
        if not mid:
            continue
        try:
            out[mid] = (
                Decimal(str(pricing.get("prompt", "0"))),
                Decimal(str(pricing.get("completion", "0"))),
            )
        except Exception:
            continue
    return out

def resolve_pricing(
    model: str,
    fallback_pricing: dict[str, tuple[Decimal, Decimal]],
    live_cache: dict[str, tuple[Decimal, Decimal]] | None = None,
) -> tuple[Decimal, Decimal, str]:
    """
    Resolve per-token pricing for a model.
    Returns (prompt_price, completion_price, source).
    Priority: live OpenRouter catalog > fallback table > partial match > zero.
    """
    mid = canonical_model_id(model)
    if live_cache and mid in live_cache:
        return live_cache[mid][0], live_cache[mid][1], "openrouter_catalog"
    if mid in fallback_pricing:
        return fallback_pricing[mid][0], fallback_pricing[mid][1], "fallback_table"
    # Partial fallback for proxy-prefixed model IDs
    for key, val in fallback_pricing.items():
        if ":free" in mid and ":free" not in key:
            continue
        if key in mid or mid in key:
            return val[0], val[1], f"fallback_partial:{key}"
    return Decimal("0"), Decimal("0"), "unknown"

def estimate_cost_usd(
    usage: Dict[str, int],
    input_per_million: float = 0.0,
    output_per_million: float = 0.0,
) -> float:
    """Simple cost estimate from usage + per-million-token prices."""
    return (
        usage.get("prompt_tokens", 0) / 1_000_000 * input_per_million
        + usage.get("completion_tokens", 0) / 1_000_000 * output_per_million
    )

def token_cost_from_pricing(
    model: str,
    usage: Dict[str, Any],
    fallback_pricing: dict[str, tuple[Decimal, Decimal]],
    live_cache: dict[str, tuple[Decimal, Decimal]] | None = None,
) -> tuple[float, str]:
    """
    Compute cost in USD for a single API call.
    Returns (cost_usd, source).
    Uses usage.cost / upstream_inference_cost if present, else resolves pricing.
    """
    # Primary: direct cost field from the API response. Some callers normalize
    # this as cost_usd for DB/reporting compatibility, so accept either key.
    direct_cost = usage.get("cost") or usage.get("cost_usd") or 0
    if direct_cost and direct_cost > 0:
        return float(direct_cost), "api_response"
    # Secondary: upstream_inference_cost in cost_details
    upstream = (usage.get("cost_details") or {}).get("upstream_inference_cost")
    if upstream:
        return float(upstream), "upstream_inference_cost"
    # Tertiary: compute from pricing tables
    prompt_price, completion_price, source = resolve_pricing(
        model, fallback_pricing, live_cache
    )
    prompt_tokens = Decimal(int(usage.get("prompt_tokens") or 0))
    completion_tokens = Decimal(int(usage.get("completion_tokens") or 0))
    cost = prompt_tokens * prompt_price + completion_tokens * completion_price
    return float(cost), source

# ─── DB Persistence ────────────────────────────────────────────────────

def connect_db(path: str | Path) -> sqlite3.Connection:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.executescript(f'''
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', '{SCHEMA_VERSION}');
    CREATE TABLE IF NOT EXISTS benchmark_runs (
      run_id TEXT PRIMARY KEY, benchmark_name TEXT NOT NULL, benchmark_version TEXT NOT NULL, suite_version TEXT NOT NULL,
      provider TEXT NOT NULL, model TEXT NOT NULL, base_url TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT,
      status TEXT NOT NULL, total_cases INTEGER DEFAULT 0, passed_cases INTEGER DEFAULT 0, score REAL DEFAULT 0,
      avg_latency_ms REAL DEFAULT 0, prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0, total_tokens INTEGER DEFAULT 0,
      cost_usd REAL DEFAULT 0, cost_estimated INTEGER DEFAULT 1, args_json TEXT DEFAULT '{{}}', notes TEXT DEFAULT '', error TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS benchmark_cases (
      id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, case_id TEXT NOT NULL, category TEXT NOT NULL,
      prompt TEXT NOT NULL, expected TEXT DEFAULT '', response TEXT DEFAULT '', passed INTEGER NOT NULL, score REAL NOT NULL,
      latency_ms INTEGER DEFAULT 0, prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0, total_tokens INTEGER DEFAULT 0,
      cost_usd REAL DEFAULT 0, cost_estimated INTEGER DEFAULT 1, error TEXT DEFAULT '', notes TEXT DEFAULT '', raw_json TEXT DEFAULT '', created_at TEXT NOT NULL,
      FOREIGN KEY(run_id) REFERENCES benchmark_runs(run_id)
    );
    CREATE TABLE IF NOT EXISTS benchmark_usage (
      id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
      prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0, total_tokens INTEGER DEFAULT 0, cost_usd REAL DEFAULT 0,
      cost_estimated INTEGER DEFAULT 1, created_at TEXT NOT NULL, FOREIGN KEY(run_id) REFERENCES benchmark_runs(run_id)
    );
    ''')
    return con

def start_run(con: sqlite3.Connection, run_id: str, benchmark_name: str, args: argparse.Namespace, target: Target) -> None:
    con.execute("""INSERT INTO benchmark_runs (run_id, benchmark_name, benchmark_version, suite_version, provider, model, base_url, started_at, status, args_json, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, ?)""", (run_id, benchmark_name, args.benchmark_version, args.suite_version, target.provider, target.model, target.base_url, utc_now(), json.dumps(vars(args), sort_keys=True), args.notes))
    con.commit()

def record_case(con: sqlite3.Connection, run_id: str, r: CaseResult) -> None:
    con.execute("""INSERT INTO benchmark_cases (run_id, case_id, category, prompt, expected, response, passed, score, latency_ms, prompt_tokens, completion_tokens, total_tokens, cost_usd, cost_estimated, error, notes, raw_json, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (run_id, r.case_id, r.category, r.prompt, r.expected, r.response, int(r.passed), r.score, r.latency_ms, r.prompt_tokens, r.completion_tokens, r.total_tokens, r.cost_usd, int(r.cost_estimated), r.error, r.notes, r.raw_json, utc_now()))
    con.commit()

def finish_run(con: sqlite3.Connection, run_id: str, status: str = "completed", error: str = "") -> None:
    row = con.execute("""SELECT COUNT(*) total, COALESCE(SUM(passed),0) passed, COALESCE(AVG(score),0) score, COALESCE(AVG(latency_ms),0) avg_latency,
      COALESCE(SUM(prompt_tokens),0) prompt_tokens, COALESCE(SUM(completion_tokens),0) completion_tokens, COALESCE(SUM(total_tokens),0) total_tokens,
      COALESCE(SUM(cost_usd),0) cost_usd, COALESCE(MIN(cost_estimated),1) exact_present FROM benchmark_cases WHERE run_id=?""", (run_id,)).fetchone()
    con.execute("""UPDATE benchmark_runs SET completed_at=?, status=?, total_cases=?, passed_cases=?, score=?, avg_latency_ms=?, prompt_tokens=?, completion_tokens=?, total_tokens=?, cost_usd=?, cost_estimated=?, error=? WHERE run_id=?""",
      (utc_now(), status, row['total'], row['passed'], row['score'], row['avg_latency'], row['prompt_tokens'], row['completion_tokens'], row['total_tokens'], row['cost_usd'], 1 if row['exact_present'] == 1 else 0, error, run_id))
    con.execute("""INSERT INTO benchmark_usage(run_id, provider, model, prompt_tokens, completion_tokens, total_tokens, cost_usd, cost_estimated, created_at)
      SELECT run_id, provider, model, prompt_tokens, completion_tokens, total_tokens, cost_usd, cost_estimated, ? FROM benchmark_runs WHERE run_id=?""", (utc_now(), run_id))
    con.commit()

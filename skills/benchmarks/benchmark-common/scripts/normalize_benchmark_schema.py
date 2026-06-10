#!/usr/bin/env python3
"""Create common read-only benchmark views for legacy benchmark DB schemas.

The benchmark-common contract standardizes on benchmark_runs, benchmark_cases,
and benchmark_usage. Some older suites still store data in suite-specific tables.
This script creates compatibility views named common_benchmark_* so report
regeneration can read a stable shape without destructive table migrations.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

COMMON_RUNS_COLUMNS = (
    "run_id", "benchmark_name", "benchmark_version", "suite_version",
    "provider", "model", "base_url", "started_at", "completed_at", "status",
    "total_cases", "passed_cases", "score", "avg_latency_ms", "prompt_tokens",
    "completion_tokens", "total_tokens", "cost_usd", "cost_estimated",
    "args_json", "notes", "error",
)

COMMON_CASES_COLUMNS = (
    "id", "run_id", "case_id", "category", "prompt", "expected", "response",
    "passed", "score", "latency_ms", "prompt_tokens", "completion_tokens",
    "total_tokens", "cost_usd", "cost_estimated", "error", "notes",
    "raw_json", "created_at",
)

COMMON_USAGE_COLUMNS = (
    "id", "run_id", "provider", "model", "prompt_tokens", "completion_tokens",
    "total_tokens", "cost_usd", "cost_estimated", "created_at",
)


def table_exists(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name=?",
        (name,),
    ).fetchone()
    return bool(row)


def columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in con.execute(f'PRAGMA table_info("{table}")')}


def drop_views(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        DROP VIEW IF EXISTS common_benchmark_runs;
        DROP VIEW IF EXISTS common_benchmark_cases;
        DROP VIEW IF EXISTS common_benchmark_usage;
        """
    )


def create_passthrough_views(con: sqlite3.Connection) -> bool:
    if not table_exists(con, "benchmark_runs"):
        return False
    con.executescript(
        """
        CREATE VIEW common_benchmark_runs AS SELECT * FROM benchmark_runs;
        CREATE VIEW common_benchmark_cases AS SELECT * FROM benchmark_cases;
        CREATE VIEW common_benchmark_usage AS SELECT * FROM benchmark_usage;
        """
    )
    return True


def create_cheap_views(con: sqlite3.Connection, benchmark_name: str) -> bool:
    if not table_exists(con, "runs"):
        return False
    cols = columns(con, "runs")
    if not {"scenario", "accuracy", "json_valid", "latency_seconds"}.issubset(cols):
        return False
    # Per-suite run_id is already present for newer rows; older rows get a stable synthetic id.
    con.executescript(
        f"""
        CREATE VIEW common_benchmark_cases AS
        SELECT
          id AS id,
          COALESCE(run_id, printf('legacy-%06d', id)) AS run_id,
          scenario AS case_id,
          scenario AS category,
          '' AS prompt,
          '' AS expected,
          COALESCE(response_text, response_sample, '') AS response,
          CASE WHEN COALESCE(status, 'success') = 'success' AND COALESCE(accuracy, 0) > 0 THEN 1 ELSE 0 END AS passed,
          COALESCE(accuracy, 0) AS score,
          CAST(COALESCE(latency_seconds, 0) * 1000 AS INTEGER) AS latency_ms,
          COALESCE(input_tokens, 0) AS prompt_tokens,
          COALESCE(output_tokens, 0) AS completion_tokens,
          COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0) AS total_tokens,
          COALESCE(cost_usd, 0) AS cost_usd,
          1 AS cost_estimated,
          COALESCE(error_message, '') AS error,
          COALESCE(scorer_notes, '') AS notes,
          COALESCE(response_text, '') AS raw_json,
          COALESCE(timestamp, '') AS created_at
        FROM runs;

        CREATE VIEW common_benchmark_runs AS
        SELECT
          COALESCE(run_id, printf('legacy-%06d', MIN(id))) AS run_id,
          '{benchmark_name}' AS benchmark_name,
          'legacy' AS benchmark_version,
          'legacy' AS suite_version,
          COALESCE(provider, 'unknown') AS provider,
          COALESCE(actual_model, requested_model, model, 'unknown') AS model,
          '' AS base_url,
          MIN(COALESCE(timestamp, '')) AS started_at,
          MAX(COALESCE(timestamp, '')) AS completed_at,
          CASE WHEN SUM(CASE WHEN COALESCE(status, 'success') != 'success' THEN 1 ELSE 0 END) > 0 THEN 'partial' ELSE 'completed' END AS status,
          COUNT(*) AS total_cases,
          SUM(CASE WHEN COALESCE(status, 'success') = 'success' AND COALESCE(accuracy, 0) > 0 THEN 1 ELSE 0 END) AS passed_cases,
          AVG(COALESCE(accuracy, 0)) AS score,
          AVG(COALESCE(latency_seconds, 0) * 1000) AS avg_latency_ms,
          SUM(COALESCE(input_tokens, 0)) AS prompt_tokens,
          SUM(COALESCE(output_tokens, 0)) AS completion_tokens,
          SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)) AS total_tokens,
          SUM(COALESCE(cost_usd, 0)) AS cost_usd,
          1 AS cost_estimated,
          '{{}}' AS args_json,
          '' AS notes,
          GROUP_CONCAT(NULLIF(error_message, ''), '; ') AS error
        FROM runs
        GROUP BY COALESCE(run_id, printf('legacy-%06d', id));

        CREATE VIEW common_benchmark_usage AS
        SELECT
          ROW_NUMBER() OVER (ORDER BY started_at, run_id) AS id,
          run_id,
          provider,
          model,
          prompt_tokens,
          completion_tokens,
          total_tokens,
          cost_usd,
          cost_estimated,
          completed_at AS created_at
        FROM common_benchmark_runs;
        """
    )
    return True


def create_orchestrator_views(con: sqlite3.Connection, benchmark_name: str) -> bool:
    if not table_exists(con, "runs"):
        return False
    cols = columns(con, "runs")
    if not {"scenario", "total", "response_text", "scorer_notes"}.issubset(cols):
        return False
    con.executescript(
        f"""
        CREATE VIEW common_benchmark_cases AS
        SELECT
          ROW_NUMBER() OVER (ORDER BY timestamp, run_id) AS id,
          run_id AS run_id,
          scenario AS case_id,
          scenario AS category,
          '' AS prompt,
          '' AS expected,
          COALESCE(response_text, '') AS response,
          CASE WHEN COALESCE(total, 0) >= 10 THEN 1 ELSE 0 END AS passed,
          COALESCE(total, 0) / 15.0 AS score,
          0 AS latency_ms,
          0 AS prompt_tokens,
          0 AS completion_tokens,
          0 AS total_tokens,
          0 AS cost_usd,
          1 AS cost_estimated,
          '' AS error,
          COALESCE(scorer_notes, '') AS notes,
          COALESCE(scorer_notes, '') AS raw_json,
          COALESCE(timestamp, '') AS created_at
        FROM runs;

        CREATE VIEW common_benchmark_runs AS
        SELECT
          run_id AS run_id,
          '{benchmark_name}' AS benchmark_name,
          'legacy' AS benchmark_version,
          'legacy' AS suite_version,
          'unknown' AS provider,
          COALESCE(model, 'unknown') AS model,
          '' AS base_url,
          COALESCE(timestamp, '') AS started_at,
          COALESCE(timestamp, '') AS completed_at,
          'completed' AS status,
          1 AS total_cases,
          CASE WHEN COALESCE(total, 0) >= 10 THEN 1 ELSE 0 END AS passed_cases,
          COALESCE(total, 0) / 15.0 AS score,
          0 AS avg_latency_ms,
          0 AS prompt_tokens,
          0 AS completion_tokens,
          0 AS total_tokens,
          0 AS cost_usd,
          1 AS cost_estimated,
          '{{}}' AS args_json,
          COALESCE(scorer_notes, '') AS notes,
          '' AS error
        FROM runs;

        CREATE VIEW common_benchmark_usage AS
        SELECT
          ROW_NUMBER() OVER (ORDER BY started_at, run_id) AS id,
          run_id,
          provider,
          model,
          prompt_tokens,
          completion_tokens,
          total_tokens,
          cost_usd,
          cost_estimated,
          completed_at AS created_at
        FROM common_benchmark_runs;
        """
    )
    return True


def normalize(db: Path, benchmark_name: str) -> str:
    con = sqlite3.connect(str(db))
    try:
        drop_views(con)
        if create_passthrough_views(con):
            kind = "passthrough"
        elif create_cheap_views(con, benchmark_name):
            kind = "legacy-runs"
        elif create_orchestrator_views(con, benchmark_name):
            kind = "legacy-orchestrator"
        else:
            raise RuntimeError(f"Unsupported schema in {db}")
        con.execute("CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        con.execute("INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('common_views', ?)", (kind,))
        con.commit()
        return kind
    finally:
        con.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--benchmark-name", required=True)
    args = ap.parse_args()
    kind = normalize(Path(args.db).expanduser(), args.benchmark_name)
    print(f"{args.db}: common views created ({kind})")


if __name__ == "__main__":
    main()

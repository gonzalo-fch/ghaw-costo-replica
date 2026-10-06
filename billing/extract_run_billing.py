#!/usr/bin/env python3
"""
Extractor de Billing para GitHub Agentic Workflows (gh-aw) — reproducible.

Objetivo: obtener, para uno o varios runs, tanto el costo de GitHub Actions
como la inferencia (AI Credits / AIC), CONSERVANDO la trazabilidad de cada dato.

Fuentes (todas verificables):
  1. GitHub Actions REST API
       GET /repos/{owner}/{repo}/actions/runs/{run_id}
       GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs
       GET /repos/{owner}/{repo}/actions/runs/{run_id}/timing
       GET /repos/{owner}/{repo}/actions/runs/{run_id}/artifacts
  2. gh-aw (artefacto de uso: tokens/AIC)
       gh aw logs --stdin --repo <repo> --json --output <dir> --artifacts usage
       gh aw audit <run_id> --repo <repo> --json --output <dir>
  3. Precios:
       - Actions: doc oficial GitHub (tabla ACTIONS_RATES_USD_PER_MIN, ver docs/)
       - AIC: 1 AIC = 0.01 USD (gh-aw AI Credits Specification sección 3.1)
       - Por modelo: models.json (gh-aw)

Principios:
  - NO redondear valores antes de guardarlos.
  - Distinguir "sin dato" (null) de "cero" (0).
  - Guardar SIEMPRE la evidencia cruda (JSON) junto al resultado.

Uso:
  python billing/extract_run_billing.py --repo vaadin/flow 36728232182
  python billing/extract_run_billing.py --repo owner/repo 111 222 --skip-ghaw
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Tarifas oficiales de GitHub Actions (USD por minuto).
# Fuente: https://docs.github.com/en/billing/managing-billing-for-your-products/
#         managing-billing-for-github-actions/about-billing-for-github-actions
# (verificadas al 2026-09; si se reejecuta en otra fecha, revisar la fuente)
# ---------------------------------------------------------------------------
ACTIONS_RATES_USD_PER_MIN = {
    "actions_linux_slim": 0.002,
    "actions_linux": 0.006,
    "actions_linux_arm": 0.005,
    "actions_windows": 0.010,
    "actions_windows_arm": 0.010,
    "actions_macos": 0.062,
}

# Mapeo EXPLICITO label de runner -> SKU de facturacion.
# Sólo se mapean labels conocidos; si no hay match => sku = None (NO inventar).
RUNNER_LABEL_TO_SKU = {
    "ubuntu-slim": "actions_linux_slim",
    "ubuntu-latest": "actions_linux",
    "ubuntu-24.04": "actions_linux",
    "ubuntu-22.04": "actions_linux",
    "ubuntu-24.04-arm": "actions_linux_arm",
    "ubuntu-22.04-arm": "actions_linux_arm",
    "windows-latest": "actions_windows",
    "windows-2022": "actions_windows",
    "windows-2025": "actions_windows",
    "windows-11-arm": "actions_windows_arm",
    "macos-latest": "actions_macos",
    "macos-14": "actions_macos",
    "macos-15": "actions_macos",
    "macos-13": "actions_macos",
}

AIC_USD = 0.01  # AI Credits Specification sección 3.1


# ---------------------------------------------------------------------------
# Utilidades de shell
# ---------------------------------------------------------------------------
def run_cmd(args, stdin_text=None, timeout=600):
    env = os.environ.copy()
    env.update({"NO_COLOR": "1", "GH_PAGER": "cat", "PAGER": "cat", "TERM": "dumb"})
    started = time.perf_counter()
    proc = subprocess.run(
        args,
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return {
        "args": list(args),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "elapsed_seconds": time.perf_counter() - started,
    }


def gh_api_json(endpoint, out_path=None):
    """GET a la API vía gh api. Guarda la respuesta cruda si out_path se indica."""
    res = run_cmd(["gh", "api", endpoint], timeout=180)
    if res["returncode"] != 0:
        raise RuntimeError(f"gh api {endpoint} fallo: {res['stderr']}")
    data = json.loads(res["stdout"])
    if out_path is not None:
        write_json(out_path, data)
    return data


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def iso_to_dt(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Componente 1: GitHub Actions
# ---------------------------------------------------------------------------
def infer_sku_from_job(job):
    labels = [str(x).lower() for x in (job.get("labels") or [])]
    for label in labels:
        if label in RUNNER_LABEL_TO_SKU:
            return RUNNER_LABEL_TO_SKU[label], label
    # self-hosted u otros: no facturable / desconocido -> no inventar
    if any("self-hosted" in x for x in labels):
        return None, (labels[0] if labels else None)
    return None, (labels[0] if labels else None)


def analyze_jobs(jobs):
    """Devuelve (jobs_analizados, agregados)."""
    analyzed = []
    total_seconds = 0.0
    total_ceil_minutes = 0.0
    total_notional_usd = 0.0
    skus = set()

    for job in jobs:
        if job.get("status") != "completed":
            continue
        started = iso_to_dt(job.get("started_at"))
        completed = iso_to_dt(job.get("completed_at"))
        if started and completed and completed >= started:
            seconds = (completed - started).total_seconds()
        else:
            seconds = None

        if job.get("conclusion") == "skipped" and not seconds:
            seconds = 0.0

        sku, matched_label = infer_sku_from_job(job)
        rate = ACTIONS_RATES_USD_PER_MIN.get(sku) if sku else None

        ceil_minutes = None
        notional_usd = None
        if seconds is not None:
            total_seconds += seconds
            ceil_minutes = math.ceil(seconds / 60.0) if seconds > 0 else 0.0
            total_ceil_minutes += ceil_minutes
            if rate is not None:
                notional_usd = ceil_minutes * rate
                total_notional_usd += notional_usd
        if sku:
            skus.add(sku)

        analyzed.append({
            "run_id": job.get("run_id"),
            "job_id": job.get("id"),
            "job_name": job.get("name"),
            "status": job.get("status"),
            "conclusion": job.get("conclusion"),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            "duration_seconds": seconds,
            "runner_name": job.get("runner_name"),
            "runner_labels_raw": json.dumps(job.get("labels") or [], ensure_ascii=False),
            "runner_label_matched": matched_label,
            "runner_sku": sku,
            "rate_usd_per_min": rate,
            "ceil_minutes": ceil_minutes,
            "actions_cost_usd_notional": notional_usd,
        })

    return analyzed, {
        "actions_vm_seconds": total_seconds,
        "actions_ceil_minutes": total_ceil_minutes,
        "actions_cost_usd_notional": total_notional_usd,
        "runner_skus": sorted(skus),
    }


# ---------------------------------------------------------------------------
# Componente 2: inferencia (AIC / tokens)
# ---------------------------------------------------------------------------
def fetch_ai_usage(repo, run_id, workdir):
    """
    Intenta obtener AIC/tokens. Devuelve dict con provenance.

    Estrategia: `gh aw logs --stdin --artifacts usage` y busca el artefacto
    de uso descargado. NO inventa: si no aparece, devuelve nulls.
    """
    out_dir = Path(workdir) / "gh-aw"
    out_dir.mkdir(parents=True, exist_ok=True)

    res = run_cmd(
        ["gh", "aw", "logs", "--stdin", "--repo", repo, "--json",
         "--output", str(out_dir), "--artifacts", "usage"],
        stdin_text=f"{run_id}\n",
        timeout=1800,
    )
    (out_dir / "gh-aw-logs.stdout.txt").write_text(res["stdout"] or "", encoding="utf-8")
    (out_dir / "gh-aw-logs.stderr.txt").write_text(res["stderr"] or "", encoding="utf-8")
    write_json(out_dir / "gh-aw-logs.command.json", {
        "args": res["args"], "returncode": res["returncode"],
        "elapsed_seconds": res["elapsed_seconds"],
    })

    result = {
        "aic": None,
        "input_tokens": None,
        "output_tokens": None,
        "cache_read_tokens": None,
        "cache_write_tokens": None,
        "reasoning_tokens": None,
        "ai_request_count": None,
        "ai_models": None,
        "aic_from_records": None,
        "ai_provenance": None,
    }

    # ------------------------------------------------------------------
    # FUENTE PREFERIDA (autoritativa de gh-aw):
    #   run_summary.json -> token_usage_summary (trae todos los tokens + total_aic)
    # ------------------------------------------------------------------
    for rsum in out_dir.rglob("run_summary.json"):
        try:
            data = json.loads(rsum.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        if str(data.get("run_id")) != str(run_id):
            continue
        tus = data.get("token_usage_summary")
        if not isinstance(tus, dict):
            continue
        result["aic"] = tus.get("total_aic")
        result["input_tokens"] = tus.get("total_input_tokens")
        result["output_tokens"] = tus.get("total_output_tokens")
        result["cache_read_tokens"] = tus.get("total_cache_read_tokens")
        result["cache_write_tokens"] = tus.get("total_cache_write_tokens")
        result["reasoning_tokens"] = tus.get("total_reasoning_tokens")  # puede no existir
        result["ai_request_count"] = tus.get("total_requests")
        by_model = tus.get("by_model") or {}
        result["ai_models"] = ",".join(sorted(by_model.keys())) or None
        result["ai_provenance"] = (
            "gh aw run_summary.json .token_usage_summary "
            f"(modelos: {result['ai_models']})"
        )
        break

    # ------------------------------------------------------------------
    # FALLBACK 1: registro del JSON de `gh aw logs` (aic reportado)
    # ------------------------------------------------------------------
    payload = None
    try:
        payload = json.loads(res["stdout"])
    except (json.JSONDecodeError, TypeError):
        payload = None

    record = None
    if isinstance(payload, dict):
        for key in ("per_run_breakdown", "runs"):
            items = payload.get(key)
            if isinstance(items, list):
                for item in items:
                    if str(item.get("run_id")) == str(run_id):
                        record = item
                        break
            if record:
                break

    if result["aic"] is None and record:
        for candidate in ("aic", "total_aic", "ai_credits", "ai_credits_total"):
            if record.get(candidate) is not None:
                result["aic"] = float(record[candidate])
                result["ai_provenance"] = f"gh aw logs json .{candidate}"
                break
    if record:
        for cand in ("input_tokens", "output_tokens", "cache_read_tokens",
                     "cache_write_tokens", "reasoning_tokens"):
            if result[cand] is None and record.get(cand) is not None:
                result[cand] = record[cand]

    # ------------------------------------------------------------------
    # FALLBACK 2: agregar token_usage.jsonl (agent/detection/evals)
    #   Nota: el nombre real del archivo usa guion bajo.
    #   Se ejecuta SIEMPRE para dejar aic_from_records (reconciliación),
    #   pero solo rellena aic/tokens si la fuente preferida no los trajo.
    # ------------------------------------------------------------------
    agg = {"input_tokens": 0, "output_tokens": 0,
           "cache_read_tokens": 0, "cache_write_tokens": 0,
           "reasoning_tokens": 0}
    aic_sum = 0.0
    requests = 0
    models = set()
    found = False
    for jsonl in out_dir.rglob("token_usage.jsonl"):
        if jsonl.parent.name != "agent":  # mismo alcance que run_summary (agente)
            continue
        for line in jsonl.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            found = True
            requests += 1
            for k in agg:
                agg[k] += rec.get(k) or 0
            aic_sum += rec.get("ai_credits_this_response") or 0
            if rec.get("model"):
                models.add(rec["model"])
    if found:
        if result["input_tokens"] is None:
            result.update(agg)
        result["aic_from_records"] = aic_sum
        if result["ai_request_count"] is None:
            result["ai_request_count"] = requests
        if result["ai_models"] is None:
            result["ai_models"] = ",".join(sorted(models)) or None
        if result["aic"] is None:
            result["aic"] = aic_sum
        if result["ai_provenance"] is None:
            result["ai_provenance"] = "token_usage.jsonl (agregado)"

    # Los tokens de razonamiento no suelen reportarse: spec sección 3.7 dice 0.
    if result["reasoning_tokens"] is None and result["input_tokens"] is not None:
        result["reasoning_tokens"] = 0

    result["aic_usd"] = None if result["aic"] is None else float(result["aic"]) * AIC_USD
    return result


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------
def extract_run(repo, run_id, root_out, skip_ghaw=False):
    run_dir = Path(root_out) / repo.replace("/", "__") / f"run-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    run = gh_api_json(f"repos/{repo}/actions/runs/{run_id}", run_dir / "run.json")
    jobs_payload = gh_api_json(
        f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100", run_dir / "jobs.json"
    )
    jobs = jobs_payload.get("jobs", jobs_payload if isinstance(jobs_payload, list) else [])

    timing = None
    try:
        timing = gh_api_json(
            f"repos/{repo}/actions/runs/{run_id}/timing", run_dir / "timing.json"
        )
    except RuntimeError as exc:
        print(f"  WARN timing no disponible: {exc}", file=sys.stderr)

    try:
        gh_api_json(
            f"repos/{repo}/actions/runs/{run_id}/artifacts", run_dir / "artifacts.json"
        )
    except RuntimeError:
        pass

    job_rows, agg = analyze_jobs(jobs)

    is_private = bool((run.get("repository") or {}).get("private"))
    actions_cost_actual = agg["actions_cost_usd_notional"] if is_private else 0.0

    ai = {
        "aic": None, "aic_usd": None,
        "input_tokens": None, "output_tokens": None,
        "cache_read_tokens": None, "cache_write_tokens": None,
        "reasoning_tokens": None, "ai_request_count": None,
        "ai_models": None, "aic_from_records": None,
        "ai_provenance": None,
    }
    if not skip_ghaw:
        try:
            ai = fetch_ai_usage(repo, run_id, run_dir)
        except Exception as exc:  # noqa: BLE001
            print(f"  WARN gh aw logs fallo: {exc}", file=sys.stderr)

    billable = None
    if timing:
        billable = None
        b = timing.get("billable") or {}
        if b:
            billable = {
                os_name: {"total_ms": v.get("total_ms"), "jobs": v.get("jobs")}
                for os_name, v in b.items()
            }

    row = {
        "repo": repo,
        "run_id": run.get("id"),
        "run_attempt": run.get("run_attempt"),
        "workflow_id": run.get("workflow_id"),
        "workflow_name": run.get("name"),
        "event": run.get("event"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "created_at": run.get("created_at"),
        "run_started_at": run.get("run_started_at"),
        "updated_at": run.get("updated_at"),
        "head_branch": run.get("head_branch"),
        "head_sha": run.get("head_sha"),
        "html_url": run.get("html_url"),
        "repo_private": is_private,
        # --- Actions ---
        "run_duration_ms_github": (timing or {}).get("run_duration_ms"),
        "actions_billable_by_os_json": json.dumps(billable, ensure_ascii=False) if billable else None,
        "jobs_count": len(jobs),
        "actions_vm_seconds": agg["actions_vm_seconds"],
        "actions_ceil_minutes": agg["actions_ceil_minutes"],
        "actions_cost_usd_notional": agg["actions_cost_usd_notional"],
        "actions_cost_usd_actual": actions_cost_actual,
        "runner_skus_json": json.dumps(agg["runner_skus"], ensure_ascii=False),
        # --- AI ---
        "aic": ai["aic"],
        "aic_usd": ai["aic_usd"],
        "input_tokens": ai["input_tokens"],
        "output_tokens": ai["output_tokens"],
        "cache_read_tokens": ai["cache_read_tokens"],
        "cache_write_tokens": ai["cache_write_tokens"],
        "reasoning_tokens": ai["reasoning_tokens"],
        "ai_request_count": ai["ai_request_count"],
        "ai_models": ai["ai_models"],
        "aic_from_records": ai["aic_from_records"],
        "ai_provenance": ai["ai_provenance"],
        # --- combinado ---
        "estimated_total_cost_usd": (
            None
            if ai["aic_usd"] is None
            else agg["actions_cost_usd_notional"] + ai["aic_usd"]
        ),
    }

    write_json(run_dir / "job_analysis.json", job_rows)
    write_json(run_dir / "billing_row.json", row)
    return row, job_rows


def main():
    parser = argparse.ArgumentParser(description="Extractor de billing traceable (gh-aw)")
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("runs", nargs="+", help="uno o más run_id")
    parser.add_argument("--out", default="billing/output", help="directorio de salida")
    parser.add_argument("--skip-ghaw", action="store_true", help="no llamar a gh aw logs")
    args = parser.parse_args()

    all_rows = []
    all_jobs = []
    for run_id in args.runs:
        print(f"Procesando {args.repo} run {run_id} ...")
        row, job_rows = extract_run(args.repo, run_id, args.out, skip_ghaw=args.skip_ghaw)
        all_rows.append(row)
        all_jobs.extend(job_rows)

    out_dir = Path(args.out) / args.repo.replace("/", "__")
    out_dir.mkdir(parents=True, exist_ok=True)

    if all_rows:
        with (out_dir / "billing_runs.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(all_rows[0].keys()))
            writer.writeheader()
            writer.writerows(all_rows)
        print("Escrito:", out_dir / "billing_runs.csv")

    if all_jobs:
        with (out_dir / "billing_jobs.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(all_jobs[0].keys()))
            writer.writeheader()
            writer.writerows(all_jobs)
        print("Escrito:", out_dir / "billing_jobs.csv")


if __name__ == "__main__":
    main()

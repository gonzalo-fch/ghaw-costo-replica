#!/usr/bin/env python3
"""
Genera el resumen de resultados preliminares (RQ1-RQ3) a partir de los datos
conservados, sin repetir la extracción. Reproduce las tablas del informe:

  Tabla 1: resultados por caso + tiempo de extracción
  Tabla 2: anatomía del consumo de IA del caso de referencia (vaadin/flow)
  Tabla 3: respuesta preliminar a RQ3 por categoría de tarea

Entradas:
  billing/output/billing_runs_all.csv    (nivel run; generado por merge_billing.py)
  billing/task_categories.csv            (orden de casos + categoría de tarea)
  billing/extraction_times.csv           (tiempos de extracción medidos)

Salida:
  billing/output/resumen_resultados.md

Uso:
  python billing/summarize_results.py
"""

from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def f(value, decimals=3):
    return "N/D" if value is None else f"{value:.{decimals}f}"


def main():
    ap = argparse.ArgumentParser(description="Resumen de resultados preliminares")
    ap.add_argument("--runs", default="billing/output/billing_runs_all.csv")
    ap.add_argument("--categories", default="billing/task_categories.csv")
    ap.add_argument("--times", default="billing/extraction_times.csv")
    ap.add_argument("--out", default="billing/output/resumen_resultados.md")
    args = ap.parse_args()

    runs_by_key = {(r["repo"], r["run_id"]): r
                   for r in read_csv(Path(args.runs))}
    times = {(t["repo"], t["run_id"]): as_float(t["extraction_seconds"])
             for t in read_csv(Path(args.times))}

    ordered = []
    for c in read_csv(Path(args.categories)):
        key = (c["repo"], c["run_id"])
        r = runs_by_key.get(key)
        if not r:
            continue
        r["_category"] = c["task_category"]
        r["_workflow"] = c["workflow"]
        ordered.append(r)

    for r in ordered:
        actions = as_float(r["actions_cost_usd_notional"])
        aic = as_float(r["aic"])
        total = as_float(r["estimated_total_cost_usd"])
        r["_actions"] = round(actions, 3) if actions is not None else None
        r["_aic"] = round(aic, 2) if aic is not None else None
        r["_total"] = round(total, 3) if total is not None else None
        aic_usd = round(aic, 2) * 0.01 if aic is not None else None
        r["_ia"] = round(aic_usd / r["_total"] * 100, 1) if (aic_usd is not None and r["_total"]) else None
        r["_time"] = times.get((r["repo"], r["run_id"]))

    totals = [r["_total"] for r in ordered if r["_total"] is not None]
    ia_pcts = [r["_ia"] for r in ordered if r["_ia"] is not None]
    actions_sum = sum(r["_actions"] for r in ordered if r["_actions"] is not None)
    aic_usd_sum = sum(round(r["_aic"], 2) * 0.01 for r in ordered if r["_aic"] is not None)

    lines = ["# Resultados preliminares (resumen)", ""]

    # Tabla 1
    lines += ["## Tabla 1. Resultados por caso y tiempo de extracción", "",
              "| Repositorio / workflow | Tarea | Actions ref. (USD) | AIC | Total est. (USD) | IA (%) | Tiempo Ext. (s) |",
              "|---|---|---|---|---|---|---|"]
    for r in ordered:
        name = f"`{r['repo']}/{r['_workflow']}`"
        lines.append(
            f"| {name} | {r['_category']} | {f(r['_actions'])} | {f(r['_aic'], 2)} | "
            f"{f(r['_total'])} | {f(r['_ia'], 1)} | {f(r['_time'], 1)} |"
        )

    # Tabla 2 (anatomía del caso de referencia = primer caso)
    if ordered:
        ref = ordered[0]
        lines += ["", f"## Tabla 2. Anatomía del consumo de IA ({ref['repo']}/{ref['_workflow']})", "",
                  "| Métrica | Valor |", "|---|---|",
                  f"| Requests al modelo | {ref['ai_request_count']} |",
                  f"| Input tokens | {ref['input_tokens']} |",
                  f"| Output tokens | {ref['output_tokens']} |",
                  f"| Cache-read tokens | {ref['cache_read_tokens']} |",
                  f"| Cache-write tokens | {ref['cache_write_tokens']} |",
                  f"| AIC canónico | {f(as_float(ref['aic']), 5)} |",
                  f"| AIC suma por request | {f(as_float(ref['aic_from_records']), 5)} |"]

    # RQ1
    lines += ["", "## RQ1 — Magnitud del costo", ""]
    if totals:
        lines.append(
            f"- n = {len(totals)}; rango = {f(min(totals))}–{f(max(totals))} USD; "
            f"mediana = {f(statistics.median(totals))} USD; suma = {f(sum(totals))} USD."
        )

    # RQ2
    lines += ["", "## RQ2 — Composición del costo", ""]
    if ia_pcts:
        lines.append(
            f"- Proporción de inferencia: rango = {f(min(ia_pcts), 1)}%–{f(max(ia_pcts), 1)}%."
        )
        lines.append(
            f"- Agregado: Actions ref. = {f(actions_sum)} USD; inferencia = {f(aic_usd_sum)} USD; "
            f"total = {f(sum(totals))} USD; inferencia = {f(aic_usd_sum / sum(totals) * 100, 1)}%."
        )

    # RQ3
    lines += ["", "## Tabla 3. RQ3 — Costo por categoría de tarea", "",
              "| Categoría | n | Total est. (USD) | IA (%) |",
              "|---|---|---|---|"]
    cats = {}
    for r in ordered:
        cats.setdefault(r["_category"], []).append(r)
    for cat, rows in cats.items():
        tots = [x["_total"] for x in rows if x["_total"] is not None]
        ias = [x["_ia"] for x in rows if x["_ia"] is not None]
        tot_str = f(tots[0]) if len(tots) == 1 else f"{f(min(tots))}–{f(max(tots))}"
        ia_str = f(ias[0], 1) if len(ias) == 1 else f"{f(min(ias), 1)}–{f(max(ias), 1)}"
        lines.append(f"| {cat} | {len(rows)} | {tot_str} | {ia_str} |")

    # Viabilidad
    ts = [r["_time"] for r in ordered if r["_time"] is not None]
    if ts:
        lines += ["", "## Viabilidad de la extracción", "",
                  f"- Tiempo por run: {f(min(ts), 1)}–{f(max(ts), 1)} s; mediana = "
                  f"{f(statistics.median(ts), 1)} s; acumulado = {f(sum(ts), 1)} s "
                  f"(5 casos, dataset en caché local)."]

    report = "\n".join(lines) + "\n"
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    print(f"Escrito: {args.out}")


if __name__ == "__main__":
    main()

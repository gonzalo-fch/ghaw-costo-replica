#!/usr/bin/env python3
"""
Genera el resumen de resultados preliminares (RQ1-RQ3) a partir de los
datos conservados, sin repetir la extracción.

Entradas:
  billing/output/billing_runs_all.csv   (nivel run; generado por merge_billing.py)
  billing/task_categories.csv           (mapa run -> categoría de tarea)

Salida:
  billing/output/resumen_resultados.md  (tabla y métricas por RQ)

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


def fmt(value, decimals=3):
    return "N/D" if value is None else f"{value:.{decimals}f}"


def fmt_pct(value):
    return "N/D" if value is None else f"{value:.1f}"


def main():
    ap = argparse.ArgumentParser(description="Resumen de resultados preliminares")
    ap.add_argument("--runs", default="billing/output/billing_runs_all.csv")
    ap.add_argument("--categories", default="billing/task_categories.csv")
    ap.add_argument("--out", default="billing/output/resumen_resultados.md")
    args = ap.parse_args()

    runs = read_csv(Path(args.runs))
    cats_path = Path(args.categories)
    cats = {}
    if cats_path.exists():
        for c in read_csv(cats_path):
            cats[(c["repo"], c["run_id"])] = c["task_category"]

    for r in runs:
        r["_total"] = as_float(r.get("estimated_total_cost_usd"))
        r["_aic_usd"] = as_float(r.get("aic_usd"))
        r["_actions"] = as_float(r.get("actions_cost_usd_notional"))
        r["_category"] = cats.get((r["repo"], r["run_id"]), "N/D")

    total = [r["_total"] for r in runs if r["_total"] is not None]
    ia_pct = [
        r["_aic_usd"] / r["_total"] * 100
        for r in runs
        if r["_total"] and r["_aic_usd"] is not None
    ]

    lines = ["# Resultados preliminares (resumen)", ""]
    lines += ["| Repositorio | Workflow | Categoría | Total (USD) | % IA |",
              "|---|---|---|---|---|"]
    for r in runs:
        pct = (r["_aic_usd"] / r["_total"] * 100) if (r["_total"] and r["_aic_usd"] is not None) else None
        lines.append(
            f"| `{r['repo']}` | {r['workflow_name']} | {r['_category']} | "
            f"{fmt(r['_total'])} | {fmt_pct(pct)} |"
        )

    lines += ["", "## RQ1 — Costo por ejecución", ""]
    if total:
        lines.append(
            f"- n = {len(total)}; mínimo = {fmt(min(total))} USD; "
            f"máximo = {fmt(max(total))} USD; mediana = {fmt(statistics.median(total))} USD."
        )

    lines += ["", "## RQ2 — Composición del costo (Actions vs. inferencia)", ""]
    if ia_pct:
        lines.append(
            f"- Proporción de inferencia: mínimo = {fmt_pct(min(ia_pct))}%; "
            f"máximo = {fmt_pct(max(ia_pct))}%; mediana = {fmt_pct(statistics.median(ia_pct))}%."
        )
        lines.append(
            f"- Proporción de GitHub Actions (nocional): "
            f"{fmt_pct(100 - max(ia_pct))}% a {fmt_pct(100 - min(ia_pct))}%."
        )

    lines += ["", "## RQ3 — Costo por categoría de tarea", ""]
    lines += ["| Categoría | Runs | Mín. (USD) | Máx. (USD) | Mediana (USD) |",
              "|---|---|---|---|---|"]
    by_cat = {}
    for r in runs:
        by_cat.setdefault(r["_category"], []).append(r["_total"])
    for cat in sorted(by_cat):
        vals = [v for v in by_cat[cat] if v is not None]
        if not vals:
            continue
        lines.append(
            f"| {cat} | {len(vals)} | {fmt(min(vals))} | {fmt(max(vals))} | "
            f"{fmt(statistics.median(vals))} |"
        )

    report = "\n".join(lines) + "\n"
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    print(f"Escrito: {args.out}")


if __name__ == "__main__":
    main()

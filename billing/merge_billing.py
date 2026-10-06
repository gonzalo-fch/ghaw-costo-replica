#!/usr/bin/env python3
"""
Consolida las salidas por repositorio en dos CSV globales.

Junta `billing/output/<owner>__<repo>/billing_runs.csv` y
`.../billing_jobs.csv` de todos los repositorios procesados y escribe:

  billing/output/billing_runs_all.csv
  billing/output/billing_jobs_all.csv

Uso:
  python billing/merge_billing.py
  python billing/merge_billing.py --out billing/output
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_rows(path: Path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="Consolida billing_runs/jobs por repo")
    ap.add_argument("--out", default="billing/output", help="directorio de salidas")
    args = ap.parse_args()

    root = Path(args.out)
    runs, jobs, n_repos = [], [], 0
    for repo_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        runs_csv = repo_dir / "billing_runs.csv"
        jobs_csv = repo_dir / "billing_jobs.csv"
        if not runs_csv.exists():
            continue
        runs += read_rows(runs_csv)
        if jobs_csv.exists():
            jobs += read_rows(jobs_csv)
        n_repos += 1
        print(f"  {repo_dir.name}: {len(read_rows(runs_csv))} run(s)")

    write_rows(root / "billing_runs_all.csv", runs)
    write_rows(root / "billing_jobs_all.csv", jobs)
    print(f"Consolidado: {n_repos} repos, {len(runs)} runs, {len(jobs)} jobs")


if __name__ == "__main__":
    main()

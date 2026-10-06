#!/usr/bin/env python3
"""
Flujo completo desde el DATASET hasta el BILLING.

Origen de los datos: https://huggingface.co/datasets/pavtch/GHAW-H

Pasos que automatiza:
  1. Leer del dataset HF el repositorio (config `repository`).
  2. Leer del dataset los workflows agénticos del repo
     (config `source_markdown_file_snapshot`, campo `path`; el `.md`),
     y derivar el workflow compilado (`*.lock.yml`).
  3. Buscar en GitHub Actions un run de ese workflow (por defecto, el más
     reciente completado cuyo job `agent` SÍ se ejecutó).
  4. Extraer el billing del run con `extract_run_billing.extract_run`
     (Actions + inferencia/AIC) y escribir el CSV.

Uso:
  # Listar workflows agénticos de un repo del dataset
  python billing/from_dataset_to_billing.py --repo vaadin/flow --list

  # Elegir workflow + run más reciente con agente y obtener billing
  python billing/from_dataset_to_billing.py --repo vaadin/flow --workflow doc-bot

  # Run concreto
  python billing/from_dataset_to_billing.py --repo vaadin/flow --run 36728232182

Nota: el endpoint HFA /rows no soporta `where`, así que se pagina y se
cachea localmente en billing/dataset_cache/ para no re-descargar.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.request
from pathlib import Path

# Importa el extractor de billing que ya existe.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_run_billing import extract_run  # noqa: E402

DATASET = "pavtch/GHAW-H"
HF_ROWS = "https://datasets-server.huggingface.co/rows"
CACHE_DIR = Path(__file__).resolve().parent / "dataset_cache"


def hf_rows(config, offset, length=100, retries=5):
    url = (f"{HF_ROWS}?dataset={DATASET.replace('/', '%2F')}"
           f"&config={config}&split=data&offset={offset}&length={length}")
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=90) as resp:
                return json.load(resp)
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(3 + 3 * i)
    raise RuntimeError(f"HF fetch fallo: {url} :: {last}")


def load_config(config, use_cache=True):
    """Descarga (o lee de cache) todas las filas de una config del dataset."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{config}.json"
    if use_cache and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    rows, offset = [], 0
    while True:
        data = hf_rows(config, offset)
        batch = [r["row"] for r in data.get("rows", [])]
        rows.extend(batch)
        if len(batch) < 100:
            break
        offset += 100
    cache.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def find_repository(repos, repo_full_name):
    for r in repos:
        if r["repo_full_name"].lower() == repo_full_name.lower():
            return r
    return None


def agentic_workflows(snapshots, repository_id):
    """Devuelve {stem: [paths .md]} para los workflows .md del repo."""
    out = {}
    for s in snapshots:
        if s.get("repository_id") != repository_id:
            continue
        path = s.get("path", "")
        if path.endswith(".md"):
            out.setdefault(Path(path).stem, set()).add(path)
    return {k: sorted(v) for k, v in sorted(out.items())}


def run_cmd(args):
    import subprocess
    return subprocess.run(args, capture_output=True, text=True)


def list_workflow_runs(repo, lock_path, per_page=20):
    """Lista runs de GitHub Actions para un workflow dado por su path."""
    res = run_cmd(["gh", "api", f"repos/{repo}/actions/workflows?per_page=100"])
    if res.returncode != 0:
        raise RuntimeError(res.stderr)
    workflows = json.loads(res.stdout).get("workflows", [])
    wf = next((w for w in workflows if w.get("path") == lock_path), None)
    if not wf:
        raise RuntimeError(f"No se encontró workflow con path {lock_path} en {repo}")
    res = run_cmd(["gh", "api",
                   f"repos/{repo}/actions/workflows/{wf['id']}/runs?per_page={per_page}"])
    if res.returncode != 0:
        raise RuntimeError(res.stderr)
    return wf, json.loads(res.stdout).get("workflow_runs", [])


def agent_ran(repo, run_id):
    """True si el job `agent` del run existe y no está skipped."""
    res = run_cmd(["gh", "api", f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100"])
    if res.returncode != 0:
        return False
    jobs = json.loads(res.stdout).get("jobs", [])
    agent = next((j for j in jobs if j.get("name") == "agent"), None)
    return bool(agent) and agent.get("conclusion") != "skipped"


def upsert_csv(path, new_rows, key_fields):
    """Inserta/actualiza filas en un CSV por clave, sin duplicar ni pisar otros runs."""
    if not new_rows:
        return
    existing = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            existing = list(csv.DictReader(fh))
    new_keys = {tuple(str(r.get(k, "")) for k in key_fields) for r in new_rows}
    kept = [r for r in existing
            if tuple(str(r.get(k, "")) for k in key_fields) not in new_keys]
    rows = kept + new_rows
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="Dataset GHAW-H -> run -> billing")
    ap.add_argument("--repo", required=True, help="owner/repo presente en el dataset")
    ap.add_argument("--workflow", help="stem del workflow .md (p.ej. doc-bot)")
    ap.add_argument("--run", help="run_id concreto")
    ap.add_argument("--list", action="store_true", help="solo listar workflows y salir")
    ap.add_argument("--out", default="billing/output")
    ap.add_argument("--no-ghaw", action="store_true")
    ap.add_argument("--max-runs", type=int, default=20)
    args = ap.parse_args()

    print("=" * 70)
    print("PASO 1 — Dataset:", DATASET)
    repos = load_config("repository")
    repo = find_repository(repos, args.repo)
    if not repo:
        raise SystemExit(f"{args.repo} NO está en el dataset")
    print(f"  Repositorio en dataset: {repo['repo_full_name']} "
          f"(repository_id={repo['repository_id']}, stars={repo.get('stars')})")

    print("=" * 70)
    print("PASO 2 — Workflows agénticos (.md) del dataset")
    snaps = load_config("source_markdown_file_snapshot")
    wfs = agentic_workflows(snaps, repo["repository_id"])
    for stem, paths in wfs.items():
        print(f"  {stem:<28} {paths[0]}  ->  {Path(paths[0]).with_suffix('.lock.yml')}")
    if not wfs:
        raise SystemExit("El dataset no registra workflows .md para este repo")
    if args.list:
        return

    stem = args.workflow or next(iter(wfs))
    if stem not in wfs:
        raise SystemExit(f"Workflow '{stem}' no está en el dataset. Opciones: {list(wfs)}")
    lock_path = str(Path(wfs[stem][0]).with_suffix(".lock.yml"))
    print(f"\n  Elegido: {stem}  ->  {lock_path}")

    print("=" * 70)
    print("PASO 3 — Runs en GitHub Actions de ese workflow")
    if args.run:
        run_id = args.run
        print("  Run indicado manualmente:", run_id)
    else:
        wf, runs = list_workflow_runs(args.repo, lock_path, args.max_runs)
        print(f"  workflow_id={wf['id']} ({wf['name']}); runs recientes: {len(runs)}")
        run_id = None
        for r in runs:
            if r.get("status") != "completed":
                continue
            ok = agent_ran(args.repo, r["id"])
            print(f"    {r['id']} {r['created_at']} {r['conclusion']} "
                  f"agent_ran={ok}")
            if ok:
                run_id = r["id"]
                break
        if not run_id:
            raise SystemExit("No se encontró un run con el agente ejecutado.")

    print("=" * 70)
    print("PASO 4 — Billing del run", run_id)
    row, job_rows = extract_run(args.repo, run_id, args.out, skip_ghaw=args.no_ghaw)

    out_dir = Path(args.out) / args.repo.replace("/", "__")
    out_dir.mkdir(parents=True, exist_ok=True)
    upsert_csv(out_dir / "billing_runs.csv", [row], ["repo", "run_id", "run_attempt"])
    upsert_csv(out_dir / "billing_jobs.csv", job_rows, ["run_id", "job_id"])
    print("Escrito (acumulando):", out_dir / "billing_runs.csv")

    print(json.dumps(row, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

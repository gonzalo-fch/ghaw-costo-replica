# Billing — Medición de costos 

Este directorio contiene el módulo de **Billing** del proyecto sobre GitHub Agentic
Workflows (gh-aw): la extracción y el cálculo de costos de ejecuciones reales.

## Preguntas de investigación

- **RQ1:** ¿Cuál es el costo de ejecutar GitHub Agentic Workflows en repositorios públicos?
- **RQ2:** ¿Cómo se distribuye el costo total entre GitHub Actions y el agente de IA?
- **RQ3:** ¿Cómo varía el costo según el tipo de tarea?

## Objetivo del módulo

El módulo calcula, para cada ejecución, dos componentes independientes del costo:

1. **GitHub Actions minutes** (cómputo del runner).
2. **Inferencia de IA**, medida por gh-aw como **AI Credits (AIC)** (`1 AIC = 0,01 USD`).

## Flujo vigente

El punto de partida es el dataset **`pavtch/GHAW-H`** → repo → workflow `.md` →
`.lock.yml` → run → billing. El conjunto de casos de esta entrega son cinco
ejecuciones de cuatro repositorios (ver el `README.md` de la raíz).

## Archivos

| Archivo | Qué es |
| --- | --- |
| [`docs/DOCUMENTACION_BILLING.md`](docs/DOCUMENTACION_BILLING.md) | Documento principal y unificado: definición, procedencia de cada columna, precios, preguntas frecuentes, validación y checklist. |
| [`from_dataset_to_billing.py`](from_dataset_to_billing.py) | **Orquestador**: parte del dataset (repo → workflow → run), delega la extracción y escribe los CSV por repositorio. |
| [`extract_run_billing.py`](extract_run_billing.py) | **Motor**: dado un `run_id`, descarga y calcula el billing (Actions API + gh-aw). No redondea; conserva evidencia cruda. |
| [`extract_run_billing.ipynb`](extract_run_billing.ipynb) | **Versión didáctica** del motor, paso a paso (mismo cálculo). |
| [`merge_billing.py`](merge_billing.py) | **Consolidador**: junta los CSV de todos los repositorios en `billing_runs_all.csv` y `billing_jobs_all.csv`. |
| [`summarize_results.py`](summarize_results.py) | **Análisis**: reproduce las tablas y métricas del informe (RQ1–RQ3) desde los datos conservados. |
| [`task_categories.csv`](task_categories.csv) | Mapa `run → categoría de tarea` (asignación manual en esta etapa) usado por el análisis (RQ3). |
| [`extraction_times.csv`](extraction_times.csv) | Tiempos de extracción medidos por caso (columna "Tiempo Ext." del informe). |
| `output/<owner>__<repo>/` | Evidencia cruda por run (run/jobs/timing/artifacts + gh-aw) y `billing_runs.csv` / `billing_jobs.csv`. |

> En una frase: `from_dataset_to_billing.py` **encuentra** el run y lo **factura**;
> `merge_billing.py` **consolida**; el notebook solo lo muestra paso a paso.

## Uso

```bash
# Flujo completo desde el dataset hasta el billing (escribe CSV)
python billing/from_dataset_to_billing.py --repo vaadin/flow --workflow doc-bot

# Extractor directo para uno o varios runs (sin llamar a gh-aw)
python billing/extract_run_billing.py --skip-ghaw --repo vaadin/flow 36728232182

# Consolidar todos los repositorios procesados
python billing/merge_billing.py

# Resumen de resultados (RQ1-RQ3) desde los datos conservados
python billing/summarize_results.py
```

Salidas: `billing_runs.csv` (nivel run) y `billing_jobs.csv` (nivel job) dentro de
`billing/output/<owner>__<repo>/`, más los consolidados `billing/output/billing_runs_all.csv`
y `billing/output/billing_jobs_all.csv` y el resumen `billing/output/resumen_resultados.md`.

## Definiciones clave (con fuente)

- `1 AIC = 0,01 USD` → [AI Credits Specification §3.1](https://github.github.com/gh-aw/specs/ai-credits-specification/)
- Precios de Actions → [GitHub Actions billing](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions)
- Catálogo por modelo → [models.json](https://raw.githubusercontent.com/github/gh-aw/main/pkg/cli/data/models.json)

## Advertencias

- Para **repos públicos**, GitHub **no cobra** Actions minutes: `actions_cost_usd_actual = 0`.
  `actions_cost_usd_notional` es precio de lista (útil para comparar), no un cobro real.
- `aic = null` significa **sin dato**, no "costo cero". Existen modelos sin precio en el
  catálogo para los que el AIC queda en 0 pese a haber consumo.
- El costo de Actions **no** sigue el modelo de tarifa fija de Bouzenia y Pradel
  (ICSE 2024) (`⌈t × f⌉ × 0.008`, con `f=1/2/10`); hoy depende de SO, arquitectura y
  tamaño del runner (ver `docs/DOCUMENTACION_BILLING.md`, sección 8.3).
- No se redondea ningún valor antes de guardarlo en el CSV.

# gaw_billing — Paquete de réplica (Etapa 2)

Trabajo de **Billing** del proyecto **"¿Cuánto cuesta la automatización? Un estudio
sobre la anatomía del costo de GitHub Agentic Workflows"** (Gonzalo Caniupán y Camilo
Ñanco, Universidad de La Frontera).

Este repositorio es el **instrumento de medición** y el **paquete de réplica** de la
Etapa 2.

## Preguntas de investigación

- **RQ1:** ¿Cuál es el costo de ejecutar GitHub Agentic Workflows en repositorios públicos?
- **RQ2:** ¿Cómo se distribuye el costo total entre GitHub Actions y el agente de IA?
- **RQ3:** ¿Cómo varía el costo según el tipo de tarea?

El instrumento registra además otros campos (tokens, modelo, runner, duración,
conclusión) que permiten abordar preguntas adicionales en etapas posteriores.

## Costos que mide

El costo total tiene dos componentes independientes:

1. **GitHub Actions minutes** (cómputo del runner).
2. **Inferencia de IA**, medida por gh-aw como **AI Credits (AIC)** (`1 AIC = 0,01 USD`).

Regla de oro del proyecto: **no dar por bueno un número si no podemos decir de dónde
viene, cómo se obtuvo y qué transformación recibió.**

## Conjunto de casos (resultados preliminares)

Cinco ejecuciones exitosas de cuatro repositorios del dataset
[`pavtch/GHAW-H`](https://huggingface.co/datasets/pavtch/GHAW-H), todas con el job
`agent` ejecutado y modelo `claude-sonnet-5`:

| Repositorio | Workflow | Categoría | Run | Total (USD) | % IA |
|---|---|---|---|---|---|
| `vaadin/flow` | Documentation Bot | Documentación | `36728232182` | 0,490 | 92,2 |
| `microsoft/vstest` | Issue Repro Triage | Issues/PR | `37312466277` | 0,828 | 94,0 |
| `microsoft/vstest` | Code Simplifier | Código | `37328625151` | 0,236 | 86,5 |
| `githubnext/agentics` | Daily Link Checker | Mantenimiento | `37269278813` | 0,737 | 92,4 |
| `rancher/dashboard` | Daily Issue Grooming | Issues/PR | `37235561667` | 0,236 | 87,3 |

Los resultados completos están en `billing/output/billing_runs_all.csv` (nivel run) y
`billing/output/billing_jobs_all.csv` (nivel job).

## Estructura

```
gaw_billing/
├── LICENSE                          # Licencia del código y la documentación
├── requirements.txt                 # Dependencias (solo biblioteca estándar + gh/gh-aw)
├── README.md                        # Este archivo
└── billing/
    ├── README.md                    # Detalle del módulo de billing
    ├── docs/
    │   └── DOCUMENTACION_BILLING.md # Documento principal y unificado
    ├── extract_run_billing.py       # Extractor trazable (Actions API + gh-aw)
    ├── extract_run_billing.ipynb    # Versión notebook, paso a paso
    ├── from_dataset_to_billing.py   # Flujo dataset GHAW-H -> run -> billing
    ├── merge_billing.py             # Consolida los CSV por repo
    ├── summarize_results.py         # Reproduce las tablas y métricas del informe
    ├── task_categories.csv          # Mapa run -> categoría de tarea (RQ3)
    ├── extraction_times.csv         # Tiempos de extracción medidos por caso
    └── output/
        ├── billing_runs_all.csv     # Consolidado a nivel run (5 casos)
        ├── billing_jobs_all.csv     # Consolidado a nivel job
        ├── resumen_resultados.md    # Resumen de resultados generado
        └── <owner>__<repo>/         # Evidencia cruda + CSV por repositorio
```

## Requisitos

- Python 3.10+ (solo biblioteca estándar).
- GitHub CLI `gh` autenticado: `gh auth login`.
- Extensión de gh-aw: `gh extension install github/gh-aw`.

## Reproducción

**Punto de entrada (datos conservados).** La reproducción de los resultados comienza
desde los datos ya incluidos en el repositorio:

```bash
python billing/merge_billing.py        # consolida billing/output/<repo>/billing_runs.csv
python billing/summarize_results.py    # reproduce las tablas y métricas del informe
```

No requiere red ni autenticación. Produce `billing/output/billing_runs_all.csv`,
`billing/output/billing_jobs_all.csv` y `billing/output/resumen_resultados.md`.

**Re-extracción desde la fuente (opcional).** Regenerar los datos desde cero requiere
`gh` autenticado y la extensión `gh-aw`; la primera ejecución descarga y cachea el
dataset GHAW-H (~75 MB):

```bash
python billing/from_dataset_to_billing.py --repo vaadin/flow --run 36728232182
python billing/from_dataset_to_billing.py --repo microsoft/vstest --run 37312466277
python billing/from_dataset_to_billing.py --repo microsoft/vstest --run 37328625151
python billing/from_dataset_to_billing.py --repo githubnext/agentics --run 37269278813
python billing/from_dataset_to_billing.py --repo rancher/dashboard --run 37235561667

python billing/merge_billing.py
python billing/summarize_results.py
```

Salidas por repositorio en `billing/output/<owner>__<repo>/`: `billing_runs.csv`
(nivel run), `billing_jobs.csv` (nivel job) y la evidencia cruda por run.

> **Restricciones de reproducibilidad.** La re-extracción depende de la API de GitHub y
> de la retención de artefactos (≈90 días), por lo que el AIC podría no estar disponible
> para runs antiguos. **Ningún resultado presentado se ve afectado**, porque la evidencia
> cruda de los cinco casos está conservada en el repositorio y permite reproducir las
> métricas sin re-extraer.

## Procedencia de los datos

- **Fuente:** dataset **GHAW-H** (Valenzuela-Toledo, Kehrer y Panichella, v0.1.2, 2026;
  DOI 10.5281/zenodo.22084012), con repositorios públicos e historial de workflows agénticos.
- **Acceso:** API REST de GitHub (`actions/runs`, `jobs`, `timing`, `artifacts`) y el
  artefacto `usage` de gh-aw.
- **Fecha de extracción:** 2026-10-05.
- **Criterios de selección:** repositorio presente en GHAW-H; workflow con definición
  `.md`; run `completed` con el job `agent` ejecutado (no `skipped`); modelo con precio
  en el catálogo (se descartaron runs con `AIC = 0` por modelo sin precio); un run por workflow.
- **Herramientas y versiones:** Python 3.10+, GitHub CLI `gh`, extensión `gh-aw` v0.86.2,
  dataset GHAW-H v0.1.2.
- **Transformaciones:** por job, `C_Actions = Σ ⌈t_j⌉ · r_j` (minutos redondeados a la
  unidad superior × tarifa del SKU); `C_IA = AIC × 0,01`; `C_run = C_Actions + C_IA`.
  No se redondea ningún valor antes de guardarlo (detalle en
  `billing/docs/DOCUMENTACION_BILLING.md`).
- **Clasificación por tarea (RQ3):** la categoría de cada run se asigna **manualmente**
  en `billing/task_categories.csv` a partir del propósito declarado en el `.md`. Esta
  etapa usa un único codificador; queda pendiente la verificación por un segundo codificador.

## Resultados por pregunta de investigación

- **RQ1** — El costo total estimado varía entre **0,236 y 0,828 USD** por ejecución
  (mediana ≈ 0,490 USD).
- **RQ2** — La inferencia del agente **domina** la composición del costo: entre
  **86,5% y 94,0%** del total; GitHub Actions aporta entre 6,0% y 13,5%.
- **RQ3** — El esquema de clasificación se aplica a las cuatro categorías
  (documentación, issues/PR, código, mantenimiento); la comparación entre tipos de
  tarea es indicativa con cinco casos.

## Estado

**Implementado:** identificación de repos/workflows del dataset, hallazgo de runs con
`agent` ejecutado, extracción conjunta de Actions y AIC, conservación de evidencia cruda
y consolidación en CSV.

**Pendiente:** escalar la extracción al conjunto completo, validar el esquema de
clasificación con más casos y calcular las distribuciones y comparaciones del análisis.

## Paquete de réplica

- Repositorio de GitHub: <https://github.com/gonzalo-fch/ghaw-costo-replica>
- Registro en Zenodo (DOI): `https://doi.org/10.5281/zenodo.<ID>` (pendiente de publicación)
- Versión (tag/commit): `<TAG-o-SHA>`

El paquete es parcial y se ampliará durante el desarrollo de la investigación.

## Documentación

- [`billing/docs/DOCUMENTACION_BILLING.md`](billing/docs/DOCUMENTACION_BILLING.md):
  procedencia de cada columna, precios, disponibilidad de datos, FAQ y checklist.
- [`billing/README.md`](billing/README.md): resumen del módulo y uso.

## Notas metodológicas

- `1 AIC = 0,01 USD` es una definición normativa de gh-aw, no un supuesto.
- En repositorios **públicos** GitHub no cobra los runners estándar: se distingue
  costo **facturado** (`actions_cost_usd_actual = 0`) de **precio de lista**
  (`actions_cost_usd_notional`).
- `aic = null` significa **sin dato**, nunca costo cero.
- No se redondea ningún valor antes de guardarlo en el CSV.

## Licencia

Código y documentación bajo licencia **MIT** (ver [`LICENSE`](LICENSE)). La evidencia
cruda pertenece a los repositorios de origen; el dataset GHAW-H conserva su propia licencia.

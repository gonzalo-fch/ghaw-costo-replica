# Resultados preliminares (resumen)

## Tabla 1. Resultados por caso y tiempo de extracción

| Repositorio / workflow | Tarea | Actions ref. (USD) | AIC | Total est. (USD) | IA (%) | Tiempo Ext. (s) |
|---|---|---|---|---|---|---|
| `vaadin/flow/doc-bot` | Documentación | 0.038 | 45.17 | 0.490 | 92.2 | 15.2 |
| `microsoft/vstest/issue-repro-triage` | Issues/PR | 0.050 | 77.81 | 0.828 | 94.0 | 20.9 |
| `microsoft/vstest/code-simplifier` | Código | 0.032 | 20.43 | 0.236 | 86.6 | 20.2 |
| `githubnext/agentics/link-checker` | Mantenimiento | 0.056 | 68.07 | 0.737 | 92.4 | 20.0 |
| `rancher/dashboard/daily-issue-grooming` | Issues/PR | 0.030 | 20.58 | 0.236 | 87.2 | 16.6 |

## Tabla 2. Anatomía del consumo de IA (vaadin/flow/doc-bot)

| Métrica | Valor |
|---|---|
| Requests al modelo | 14 |
| Input tokens | 11719 |
| Output tokens | 6873 |
| Cache-read tokens | 886469 |
| Cache-write tokens | 82262 |
| AIC canónico | 45.16788 |
| AIC suma por request | 71.26752 |

## RQ1 — Magnitud del costo

- n = 5; rango = 0.236–0.828 USD; mediana = 0.490 USD; suma = 2.527 USD.

## RQ2 — Composición del costo

- Proporción de inferencia: rango = 86.6%–94.0%.
- Agregado: Actions ref. = 0.206 USD; inferencia = 2.321 USD; total = 2.527 USD; inferencia = 91.8%.

## Tabla 3. RQ3 — Costo por categoría de tarea

| Categoría | n | Total est. (USD) | IA (%) |
|---|---|---|---|
| Documentación | 1 | 0.490 | 92.2 |
| Issues/PR | 2 | 0.236–0.828 | 87.2–94.0 |
| Código | 1 | 0.236 | 86.6 |
| Mantenimiento | 1 | 0.737 | 92.4 |

## Viabilidad de la extracción

- Tiempo por run: 15.2–20.9 s; mediana = 20.0 s; acumulado = 92.9 s (5 casos, dataset en caché local).

# Resultados preliminares (resumen)

| Repositorio | Workflow | Categoría | Total (USD) | % IA |
|---|---|---|---|---|
| `githubnext/agentics` | Daily Link Checker & Fixer | Mantenimiento | 0.737 | 92.4 |
| `microsoft/vstest` | Issue Repro Triage & Auto-Fix 🔍 | Issues/Pull requests | 0.828 | 94.0 |
| `microsoft/vstest` | Code Simplifier | Generación o revisión de código | 0.236 | 86.5 |
| `rancher/dashboard` | Daily Issue Grooming | Issues/Pull requests | 0.236 | 87.3 |
| `vaadin/flow` | Documentation Bot | Documentación | 0.490 | 92.2 |

## RQ1 — Costo por ejecución

- n = 5; mínimo = 0.236 USD; máximo = 0.828 USD; mediana = 0.490 USD.

## RQ2 — Composición del costo (Actions vs. inferencia)

- Proporción de inferencia: mínimo = 86.5%; máximo = 94.0%; mediana = 92.2%.
- Proporción de GitHub Actions (nocional): 6.0% a 13.5%.

## RQ3 — Costo por categoría de tarea

| Categoría | Runs | Mín. (USD) | Máx. (USD) | Mediana (USD) |
|---|---|---|---|---|
| Documentación | 1 | 0.490 | 0.490 | 0.490 |
| Generación o revisión de código | 1 | 0.236 | 0.236 | 0.236 |
| Issues/Pull requests | 2 | 0.236 | 0.828 | 0.532 |
| Mantenimiento | 1 | 0.737 | 0.737 | 0.737 |

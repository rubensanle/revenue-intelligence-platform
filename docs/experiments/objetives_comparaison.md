# Comparación de objectives en LightGBM

## Experimento 1 — Un corte (cutoff 2011-07-11)

| Objective | MAE | Bias | Best iter |
|---|---|---|---|
| regression (L2) | 54,77 | −4,63 | 174 |
| **regression_l1** | **52,40** | −25,23 | 72 |
| poisson | 54,01 | −11,00 | 143 |
| tweedie | 53,96 | −13,64 | 64 |

**Decisión:** `regression_l1` porque optimiza MAE directamente y necesita menos iteraciones.
El sesgo negativo es esperado (predice mediana condicional) y se documenta como trade-off.

## Experimento 2 — Backtesting completo (8 cortes)

| Objective | MAE medio | WAPE medio | MASE medio | Bias medio |
|---|---|---|---|---|
| **regression_l1** | **34,74** | **0,9127** | **0,5740** | **−17,59** |
| regression (L2) | 40,41 | 2,1649 | 0,9682 | +0,88 |

_Nota: el número de predicciones difiere entre experimentos (128.232 vs 21.372). Los WAPE no son estrictamente comparables entre ambos. Pendiente de investigar el motivo en v2._
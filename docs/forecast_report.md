# Forecasting de demanda — Online Retail II

_Generado automáticamente por `src/models/forecast_report.py`._

## 1. Problema y decisiones de diseño

- **Qué predecimos:** unidades vendidas por producto y semana.
- **Horizonte:** 4 semanas.
- **Granularidad:** producto × semana (lunes ISO).
- **Productos incluidos:** 1.076 forecastable (de 5.285).
- **Excluidos:** intermittent, high_variance, low_volume, anomaly_returns, wholesale_dependent.
- **Excluido del análisis temporal:** dic-2011 (parcial).

## 2. Baselines

Comparamos contra 5 baselines triviales:

- `mean`: media histórica.
- `naive`: última observación.
- `seasonal_naive`: misma semana del año anterior (52w).
- `moving_average`: media de las últimas 4 semanas.
- `drift`: última observación + tendencia lineal.

## 3. Modelo

- **LightGBM global** con `stock_code` y `week_of_year` como categóricas.
- **Objective:** `regression_l1` (ver `docs/experiments/objectives_comparison.md`).
- **Features:** 13 (lags 1/2/4/8/13/52, rolling means/std, week_of_year, month, horizon, product_mean).
- **Sin leakage:** todas las features se calculan con datos ≤ cutoff.

## 4. Backtesting

Rolling-origin, **8 cortes**, horizonte 4 semanas.

### Resultados por modelo

| model                  |   mae_mean |   mae_median |   wape_mean |   wape_median |   bias_mean |   n_groups |   mase_mean |   mase_median |   coverage_mean |
|:-----------------------|-----------:|-------------:|------------:|--------------:|------------:|-----------:|------------:|--------------:|----------------:|
| lightgbm_regression_l1 |    34.7437 |      13.9181 |      0.9127 |        0.5056 |    -17.5897 |       6109 |      0.574  |        0.368  |          0.8635 |
| moving_average         |    45.9405 |      21      |      1.3432 |        0.6583 |     -1.3445 |       6109 |      0.7353 |        0.5413 |        nan      |
| naive                  |    58.2675 |      23      |      1.5256 |        0.7292 |      3.2333 |       6109 |      0.8928 |        0.6033 |        nan      |
| mean                   |    50.0301 |      27.25   |      2.2122 |        0.7843 |      7.6374 |       6109 |      0.834  |        0.6642 |        nan      |
| seasonal_naive         |    67.6351 |      35      |      2.5695 |        0.9459 |     17.7468 |       6109 |      1.121  |        0.8427 |        nan      |
| drift                  |   132.287  |      40.25   |      3.592  |        1      |     62.2275 |       6109 |      1.9359 |        1.0035 |        nan      |

**Mejor modelo:** `lightgbm_regression_l1` con WAPE medio **0.9127** y MASE medio **0.5740**.

### Interpretación

- LightGBM reduce el WAPE ~32% frente al mejor baseline (moving_average).
- MASE < 1 → bate al naive in-sample en la mayoría de productos.
- Sesgo negativo (−17,6) → infra-predice, esperado con L1.
- `seasonal_naive` es peor que `naive` → con solo 2 años, la estacionalidad anual no se captura bien.

## 5. Análisis de errores

**Top 10 productos con mayor MAE medio (alto volumen, no necesariamente mal predichos):**

| stock_code   |   mae_mean |   wape_mean |   n_groups |
|:-------------|-----------:|------------:|-----------:|
| 22197        |    873.558 |    0.714649 |         48 |
| 85123A       |    783.464 |    1.04778  |         48 |
| 84077        |    665.247 |    0.702011 |         48 |
| 85099B       |    664.892 |    0.664084 |         48 |
| 21915        |    664.295 |    1.39922  |         48 |
| 22616        |    593.888 |    1.46723  |         42 |
| 21212        |    515.878 |    0.906908 |         48 |
| 21977        |    513.569 |    1.47166  |         48 |
| 15036        |    497.921 |    1.44986  |         48 |
| 84879        |    484.276 |    0.628521 |         48 |

**Top 10 productos con mayor WAPE medio (los que peor se predicen):**

| stock_code   |   mae_mean |   wape_mean |   n_groups |
|:-------------|-----------:|------------:|-----------:|
| 21181        |   340.507  |    144.63   |         48 |
| 22444        |    88.4699 |     75.3851 |         12 |
| 22241        |    48.6129 |     36.1262 |         48 |
| 22353        |    34.2064 |     34.2064 |          6 |
| 82494L       |    69.7302 |     21.7897 |         48 |
| 21830        |    66.9476 |     19.2168 |         48 |
| 21520        |    23.9871 |     19.2133 |         18 |
| 21518        |    14.8734 |     14.8734 |          6 |
| 20966        |    19.8685 |     13.4391 |         30 |
| 21656        |    26.3423 |     13.1712 |          6 |

**Interpretación:** el MAE está dominado por el volumen. El WAPE normaliza por la magnitud, así que identifica los productos que realmente se predicen mal. Un producto con MAE alto y WAPE bajo se predice bien en términos relativos (es de alto volumen).

**Error por horizonte:**

_No disponible (falta columna `horizon` en `backtest_detailed.parquet`)._

## 6. Intervalos de incertidumbre

- **Método:** conformal prediction al 80%.
- **Residuos:** calculados sobre el 20% más reciente del train de cada corte.
- **Cobertura empírica media:** 86.35%

## 7. Limitaciones

- No se predicen productos `intermittent` (Croston en v2).
- Sesgo negativo con L1 → propenso a falta de stock. Ofrecemos ajuste en simulador.
- Con 2 años de datos, la estacionalidad anual es débil.
- `wholesale_dependent` excluido: demanda puntual, no estacional.

- **Productos forecastables vs. forecast final:** de los 1.076 productos forecastable, 966 tienen ≥52 semanas de historia y se incluyen en el forecast final. Los 110 restantes son productos lanzados en 2011 sin suficiente historia para `lag_52`. En v2 se podría usar un fallback a `product_mean` para incluirlos.

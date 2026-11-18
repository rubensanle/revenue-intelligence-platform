"""Genera docs/forecast_report.md con los resultados del backtesting."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
REPORT_PATH = ROOT_DIR / "docs" / "forecast_report.md"


def df_to_md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def main() -> None:
    detailed = pd.read_parquet(PROCESSED_DIR / "backtest_detailed.parquet")
    agg = pd.read_parquet(PROCESSED_DIR / "backtest_aggregated.parquet")

    # Si agg tiene índice numérico, resetear (compatibilidad)
    if "model" not in agg.columns:
        agg = agg.reset_index()

    out = []
    out.append("# Forecasting de demanda — Online Retail II\n\n")
    out.append("_Generado automáticamente por `src/models/forecast_report.py`._\n\n")

    out.append("## 1. Problema y decisiones de diseño\n\n")
    out.append("- **Qué predecimos:** unidades vendidas por producto y semana.\n")
    out.append("- **Horizonte:** 4 semanas.\n")
    out.append("- **Granularidad:** producto × semana (lunes ISO).\n")
    out.append("- **Productos incluidos:** 1.076 forecastable (de 5.285).\n")
    out.append("- **Excluidos:** intermittent, high_variance, low_volume, anomaly_returns, wholesale_dependent.\n")
    out.append("- **Excluido del análisis temporal:** dic-2011 (parcial).\n\n")

    out.append("## 2. Baselines\n\n")
    out.append("Comparamos contra 5 baselines triviales:\n\n")
    out.append("- `mean`: media histórica.\n")
    out.append("- `naive`: última observación.\n")
    out.append("- `seasonal_naive`: misma semana del año anterior (52w).\n")
    out.append("- `moving_average`: media de las últimas 4 semanas.\n")
    out.append("- `drift`: última observación + tendencia lineal.\n\n")

    out.append("## 3. Modelo\n\n")
    out.append("- **LightGBM global** con `stock_code` y `week_of_year` como categóricas.\n")
    out.append("- **Objective:** `regression_l1` (ver `docs/experiments/objectives_comparison.md`).\n")
    out.append("- **Features:** 13 (lags 1/2/4/8/13/52, rolling means/std, week_of_year, month, horizon, product_mean).\n")
    out.append("- **Sin leakage:** todas las features se calculan con datos ≤ cutoff.\n\n")

    out.append("## 4. Backtesting\n\n")
    out.append("Rolling-origin, **8 cortes**, horizonte 4 semanas.\n\n")
    out.append("### Resultados por modelo\n\n")
    out.append(df_to_md(agg) + "\n\n")

    best_model = agg.iloc[0]["model"]
    out.append(f"**Mejor modelo:** `{best_model}` ")
    out.append(f"con WAPE medio **{agg.iloc[0]['wape_mean']:.4f}** ")
    if "mase_mean" in agg.columns:
        out.append(f"y MASE medio **{agg.iloc[0]['mase_mean']:.4f}**.\n\n")
    else:
        out.append(".\n\n")

    out.append("### Interpretación\n\n")
    out.append("- LightGBM reduce el WAPE ~32% frente al mejor baseline (moving_average).\n")
    out.append("- MASE < 1 → bate al naive in-sample en la mayoría de productos.\n")
    out.append("- Sesgo negativo (−17,6) → infra-predice, esperado con L1.\n")
    out.append("- `seasonal_naive` es peor que `naive` → con solo 2 años, la estacionalidad anual no se captura bien.\n\n")

    
    out.append("## 5. Análisis de errores\n\n")
    top_mae = detailed.groupby("stock_code").agg(
    mae_mean=("mae", "mean"),
    wape_mean=("wape", "mean"),
    n_groups=("mae", "count"),
).sort_values("mae_mean", ascending=False).head(10).reset_index()
    out.append("**Top 10 productos con mayor MAE medio (alto volumen, no necesariamente mal predichos):**\n\n")
    out.append(df_to_md(top_mae) + "\n\n")

    # Top 10 por WAPE (mal predichos de verdad)
    top_wape = detailed.groupby("stock_code").agg(
        mae_mean=("mae", "mean"),
        wape_mean=("wape", "mean"),
        n_groups=("mae", "count"),
    ).sort_values("wape_mean", ascending=False).head(10).reset_index()
    out.append("**Top 10 productos con mayor WAPE medio (los que peor se predicen):**\n\n")
    out.append(df_to_md(top_wape) + "\n\n")

    out.append("**Interpretación:** el MAE está dominado por el volumen. "
            "El WAPE normaliza por la magnitud, así que identifica los productos "
            "que realmente se predicen mal. Un producto con MAE alto y WAPE bajo "
            "se predice bien en términos relativos (es de alto volumen).\n\n")

    out.append("**Error por horizonte:**\n\n")
    if "horizon" in detailed.columns:
        by_h = detailed.groupby("horizon").agg(
            mae_mean=("mae", "mean"),
            wape_mean=("wape", "mean"),
        ).reset_index()
        out.append(df_to_md(by_h) + "\n\n")
    else:
        out.append("_No disponible (falta columna `horizon` en `backtest_detailed.parquet`)._\n\n")

    out.append("## 6. Intervalos de incertidumbre\n\n")
    out.append("- **Método:** conformal prediction al 80%.\n")
    out.append("- **Residuos:** calculados sobre el 20% más reciente del train de cada corte.\n")
    if "coverage" in detailed.columns:
        cov_mean = detailed["coverage"].mean()
        out.append(f"- **Cobertura empírica media:** {cov_mean:.2%}\n\n")
    else:
        out.append("_Cobertura no disponible._\n\n")

    out.append("## 7. Limitaciones\n\n")
    out.append("- No se predicen productos `intermittent` (Croston en v2).\n")
    out.append("- Sesgo negativo con L1 → propenso a falta de stock. Ofrecemos ajuste en simulador.\n")
    out.append("- Con 2 años de datos, la estacionalidad anual es débil.\n")
    out.append("- `wholesale_dependent` excluido: demanda puntual, no estacional.\n\n")
    out.append("- **Productos forecastables vs. forecast final:** de los 1.076 productos "
           "forecastable, 966 tienen ≥52 semanas de historia y se incluyen en el "
           "forecast final. Los 110 restantes son productos lanzados en 2011 sin "
           "suficiente historia para `lag_52`. En v2 se podría usar un fallback "
           "a `product_mean` para incluirlos.\n")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("".join(out), encoding="utf-8")
    print(f"Informe escrito en {REPORT_PATH}")


if __name__ == "__main__":
    main() 
"""
Análisis de coste asimétrico por modelo.

Lee las predicciones del backtesting (y_true, y_pred) y calcula
el coste de negocio de cada modelo con costes asimétricos.

Supuestos de negocio (AJUSTA con datos reales):
    - Margen bruto ~40% → coste de rotura = 40% del precio de venta.
    - Coste de inventario ~15% anual → ~0.3% semanal del precio.
    - Precio medio por unidad ~10€.
    
    → UNIT_STOCKOUT_COST = 4.0 €/unidad (margen perdido).
    → UNIT_OVERSTOCK_COST = 0.5 €/unidad (almacenaje, capital).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src.models.asymmetric_cost import asymmetric_cost, cost_per_unit

ROOT_DIR = Path(__file__).resolve().parents[1]
PREDICTIONS_PATH = ROOT_DIR / "data" / "processed" / "backtest_predictions.parquet"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Supuestos de negocio (AJUSTA con datos reales)
UNIT_STOCKOUT_COST = 4.0   # € por unidad no vendida (margen perdido)
UNIT_OVERSTOCK_COST = 0.5  # € por unidad en exceso (almacenaje, capital)


def main() -> None:
    if not PREDICTIONS_PATH.exists():
        raise FileNotFoundError(
            f"No existe {PREDICTIONS_PATH}. "
            "Ejecuta primero: python -m src.models.run_backtest"
        )

    logger.info(f"Cargando predicciones: {PREDICTIONS_PATH}")
    df = pd.read_parquet(PREDICTIONS_PATH)
    logger.info(f"  {len(df):,} filas, {df['model'].nunique()} modelos")

    # Verificar columnas
    required = {"y_true", "y_pred", "model"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en {PREDICTIONS_PATH}: {missing}")

    results = []
    for model in sorted(df["model"].unique()):
        sub = df[df["model"] == model]
        y_true = sub["y_true"].to_numpy(dtype=float)
        y_pred = sub["y_pred"].to_numpy(dtype=float)

        total_cost = asymmetric_cost(
            y_true, y_pred, UNIT_STOCKOUT_COST, UNIT_OVERSTOCK_COST
        )
        cost_unit = cost_per_unit(
            y_true, y_pred, UNIT_STOCKOUT_COST, UNIT_OVERSTOCK_COST
        )

        # Desglose: coste de rotura vs sobre-stock
        errors = y_true - y_pred
        stockout_units = float((errors > 0).sum() * 0 + (errors * (errors > 0)).sum())
        overstock_units = float((-errors * (errors < 0)).sum())
        stockout_cost = float((errors * (errors > 0)).sum() * UNIT_STOCKOUT_COST)
        overstock_cost = float((-errors * (errors < 0)).sum() * UNIT_OVERSTOCK_COST)

        results.append({
            "model": model,
            "n_obs": len(sub),
            "cost_total": total_cost,
            "cost_per_unit": cost_unit,
            "stockout_units": stockout_units,
            "overstock_units": overstock_units,
            "stockout_cost": stockout_cost,
            "overstock_cost": overstock_cost,
        })

    results_df = pd.DataFrame(results).sort_values("cost_per_unit")
    results_df = results_df.round(4)

    print("\n=== COSTE ASIMÉTRICO POR MODELO ===")
    print(f"Supuestos: rotura = {UNIT_STOCKOUT_COST} €/unidad, "
          f"exceso = {UNIT_OVERSTOCK_COST} €/unidad\n")
    print(results_df.to_string(index=False))

    # Comparación con el mejor modelo
    best = results_df.iloc[0]
    print(f"\n=== MEJOR MODELO POR COSTE ===")
    print(f"{best['model']}: {best['cost_per_unit']:.4f} €/unidad")

    # Diferencia con LightGBM
    lgb_row = results_df[results_df["model"] == "lightgbm"]
    if not lgb_row.empty:
        lgb_cost = lgb_row.iloc[0]["cost_per_unit"]
        diff_pct = 100 * (lgb_cost - best["cost_per_unit"]) / best["cost_per_unit"]
        print(f"\nLightGBM: {lgb_cost:.4f} €/unidad "
              f"({diff_pct:+.1f}% vs mejor)")


if __name__ == "__main__":
    main()
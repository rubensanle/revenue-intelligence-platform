"""Compara regression_l1 vs regression en backtesting completo."""

import logging
from pathlib import Path
import pandas as pd

from src.models.pipeline import aggregate_results, run_backtesting

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CONFIGS = {
    "regression_l1": {"objective": "regression_l1", "metric": "mae"},
    "regression": {"objective": "regression", "metric": "l2"},
}

results = []
for name, params in CONFIGS.items():
    logger.info(f"\n=== Entrenando con objective={name} ===")
    metrics = run_backtesting(
        n_splits=8,
        horizon=4,
        objective=params["objective"],
        metric=params["metric"],
        predictions_path=OUTPUT_DIR / f"backtest_predictions_{name}.parquet",
    )
    agg = aggregate_results(metrics)
    lgb = agg[agg.index == f"lightgbm_{name}"]
    if not lgb.empty:
        results.append({
            "objective": name,
            "mae_mean": lgb["mae_mean"].iloc[0],
            "wape_mean": lgb["wape_mean"].iloc[0],
            "mase_mean": lgb["mase_mean"].iloc[0] if "mase_mean" in lgb.columns else None,
            "mase_median": lgb["mase_median"].iloc[0] if "mase_median" in lgb.columns else None,
            "bias_mean": lgb["bias_mean"].iloc[0],
        })

results_df = pd.DataFrame(results)
print("\n=== COMPARACIÓN DE OBJECTIVES ===")
print(results_df.to_string(index=False))
results_df.to_csv(OUTPUT_DIR / "objective_comparison.csv", index=False)
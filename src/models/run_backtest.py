"""Script de ejecución del backtesting completo."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src.models.pipeline import aggregate_results, run_backtesting

ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT_DIR / "data" / "processed"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("=== Iniciando backtesting ===")
    results = run_backtesting(n_splits=8, horizon=4)

    # Guardar resultados detallados
    detailed_path = OUTPUT_DIR / "backtest_detailed.parquet"
    results.to_parquet(detailed_path, index=False)
    logger.info(f"Resultados detallados: {detailed_path}")

    # Guardar agregados
    agg = aggregate_results(results)
    agg_path = OUTPUT_DIR / "backtest_aggregated.parquet"
    agg.to_parquet(agg_path, index=False)
    logger.info(f"Resultados agregados: {agg_path}")

    print("\n=== RESUMEN POR MODELO ===\n")
    print(agg.to_string())

    print("\n=== MEJOR MODELO POR WAPE MEDIO ===")
    best = agg.index[0]
    print(f"{best}: WAPE medio = {agg.loc[best, 'wape_mean']:.4f}")


if __name__ == "__main__":
    main()
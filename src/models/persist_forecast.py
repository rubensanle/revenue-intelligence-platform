"""
Módulo D.4.3 — Persiste las predicciones finales en forecast_weekly.

Entrena el modelo con TODOS los datos disponibles hasta el cutoff global,
y predice las 4 semanas siguientes. Guarda el resultado en DuckDB como
tabla 'forecast_weekly' con:
    stock_code, week_start, horizon, y_pred, lower, upper, model, trained_at

Decisiones de diseño:
    - El cutoff global es la última semana del dataset (2011-11-28).
    - Para el modelo final, entrenamos con cutoff = cutoff_global - horizon,
      de modo que tengamos y_true para validación conformal.
    - Para predecir, usamos cutoff = cutoff_global con include_future=True.
    - El horizonte se recalcula RELATIVO al cutoff global, no al último
      dato de cada producto. Esto garantiza que h=1 sea siempre la primera
      semana después del cutoff global.
    - Productos sin suficiente historia hasta el cutoff de entrenamiento
      se excluyen (documentado en log).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from src.models.features import build_features
from src.models.lightgbm_model import predict_lightgbm, train_lightgbm
from src.models.metrics import conformal_interval
from src.models.pipeline import load_forecastable_series

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "data" / "processed" / "revenue.duckdb"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def train_final_and_forecast(horizon: int = 4) -> pd.DataFrame:
    """Entrena con todos los datos hasta el cutoff global y predice horizon semanas."""
    df = load_forecastable_series()
    global_cutoff = df["week_start"].max()
    logger.info(f"Cutoff global (última semana observada): {global_cutoff.date()}")

    # ── 1. ENTRENAMIENTO: cutoff retrocedido horizon semanas ──────────────
    #    Así tenemos y_true para validación conformal.
    train_cutoff = global_cutoff - pd.Timedelta(weeks=horizon)
    logger.info(f"Cutoff de entrenamiento: {train_cutoff.date()}")

    features_train, y_true_train = build_features(
        df,
        cutoff=train_cutoff,
        horizon=horizon,
        return_y_true=True,
        include_future=False,
    )
    features_with_target = features_train.assign(
        y_true=y_true_train
    ).reset_index(drop=True)
    logger.info(
        f"Features de entrenamiento: {len(features_with_target):,} filas, "
        f"{features_with_target['stock_code'].nunique()} productos"
    )

    # ── 2. Split temporal 80/20 para conformal ───────────────────────────
    weeks = sorted(features_with_target["week_start"].unique())
    cut_week = weeks[int(len(weeks) * 0.8)]
    train_mask = features_with_target["week_start"] < cut_week
    valid_mask = features_with_target["week_start"] >= cut_week
    logger.info(
        f"Train: {train_mask.sum():,} filas hasta {pd.Timestamp(cut_week).date()} | "
        f"Valid: {valid_mask.sum():,} filas"
    )

    # ── 3. Entrenar modelo final ─────────────────────────────────────────
    logger.info("Entrenando modelo final...")
    model = train_lightgbm(
        train_df=features_with_target[train_mask],
        valid_df=features_with_target[valid_mask],
    )

    # ── 4. Residuos conformal en validación ──────────────────────────────
    valid_preds = predict_lightgbm(model, features_with_target[valid_mask])
    residuals = np.abs(valid_preds["y_true"].values - valid_preds["y_pred"].values)
    q80 = float(np.quantile(residuals, 0.8))
    logger.info(f"Residuos validación: n={len(residuals)}, q80={q80:.2f}")

    # ── 5. PREDICCIÓN: cutoff global, include_future=True ────────────────
    features_future, _ = build_features(
        df,
        cutoff=global_cutoff,
        horizon=horizon,
        return_y_true=True,
        include_future=True,
    )

    # Filtrar solo semanas estrictamente posteriores al cutoff global
    features_future = features_future[
        features_future["week_start"] > global_cutoff
    ].copy()

    # ── 6. Recalcular horizonte RELATIVO al cutoff global ────────────────
    #    Esto es clave: productos con historia corta pueden tener horizonte
    #    mal etiquetado por build_features (relativo a su último dato).
    features_future["horizon"] = (
        (features_future["week_start"] - global_cutoff).dt.days // 7
    ).astype(int)

    n_products = features_future["stock_code"].nunique()
    logger.info(
        f"Features futuras: {len(features_future):,} filas, "
        f"{n_products} productos, horizontes {sorted(features_future['horizon'].unique())}"
    )

    # ── 7. Predecir y aplicar intervalos ─────────────────────────────────
    preds = predict_lightgbm(model, features_future)
    preds["lower"], preds["upper"] = conformal_interval(
        preds["y_pred"].values, residuals, coverage=0.8,
    )

    # ── 8. Metadatos ─────────────────────────────────────────────────────
    preds["model"] = "lightgbm_l1"
    preds["trained_at"] = datetime.now()
    if "y_true" in preds.columns:
        preds = preds.drop(columns=["y_true"])

    # Ordenar por producto y horizonte para salida legible
    preds = preds.sort_values(["stock_code", "horizon"]).reset_index(drop=True)

    return preds


def persist_forecast(df: pd.DataFrame) -> None:
    """Escribe la tabla forecast_weekly en DuckDB."""
    con = duckdb.connect(str(DB_PATH))
    try:
        con.execute("DROP TABLE IF EXISTS forecast_weekly")
        con.register("df_view", df)
        con.execute("""
            CREATE TABLE forecast_weekly AS
            SELECT
                stock_code,
                week_start::DATE AS week_start,
                horizon::INTEGER AS horizon,
                y_pred::DOUBLE AS y_pred,
                lower::DOUBLE AS lower,
                upper::DOUBLE AS upper,
                model,
                trained_at::TIMESTAMP AS trained_at
            FROM df_view
        """)
        con.unregister("df_view")
        n = con.execute("SELECT COUNT(*) FROM forecast_weekly").fetchone()[0]
        logger.info(f"forecast_weekly creada con {n:,} filas")
    finally:
        con.close()


def main() -> None:
    logger.info("=== Generando forecast final ===")
    preds = train_final_and_forecast(horizon=4)
    persist_forecast(preds)
    logger.info("=== Forecast persistido ===")

    # ── Resumen ──────────────────────────────────────────────────────────
    print("\n=== Resumen forecast_weekly ===")
    print(f"Filas: {len(preds):,}")
    print(f"Productos: {preds['stock_code'].nunique():,}")
    print(f"Semanas: {sorted(pd.to_datetime(preds['week_start']).unique())}")
    print(f"Horizontes: {sorted(preds['horizon'].unique())}")
    print(f"\nDistribución de filas por horizonte:")
    print(preds["horizon"].value_counts().sort_index().to_string())
    print(f"\nEjemplo (primeras 5 filas):")
    print(preds.head().to_string(index=False))


if __name__ == "__main__":
    main()
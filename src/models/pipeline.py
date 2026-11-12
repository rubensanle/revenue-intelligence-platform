"""
Módulo D.3 — Pipeline de backtesting completo.

Orquesta:
    1. Generación de cortes de backtesting.
    2. Para cada corte:
        a. Entrenar LightGBM con datos hasta el corte.
        b. Predecir con LightGBM.
        c. Predecir con baselines.
        d. Evaluar todos los modelos (incluyendo MASE).
        e. Guardar predicciones para análisis de coste asimétrico.
    3. Agregar resultados.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from src.models.backtest import rolling_origin_splits
from src.models.baselines import (
    drift_forecast,
    mean_forecast,
    moving_average_forecast,
    naive_forecast,
    seasonal_naive_forecast,
)
from src.models.features import build_features
from src.models.lightgbm_model import predict_lightgbm, train_lightgbm
from src.models.metrics import evaluate_forecast

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "data" / "processed" / "revenue.duckdb"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_forecastable_series() -> pd.DataFrame:
    """Carga la serie semanal de productos forecastable."""
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        df = con.execute("""
            SELECT w.stock_code, w.week_start, w.units_sold
            FROM v_weekly_sales w
            JOIN v_forecastable_products f USING (stock_code)
            WHERE f.forecastability = 'forecastable'
            ORDER BY w.stock_code, w.week_start
        """).df()
    finally:
        con.close()
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["stock_code"] = df["stock_code"].astype(str)
    return df


def _build_y_train_map(
    df_train: pd.DataFrame,
    stock_codes: list[str],
) -> dict[str, np.ndarray]:
    """Mapa {stock_code: array de units_sold} para MASE."""
    y_train_map: dict[str, np.ndarray] = {}
    for sc in stock_codes:
        g = df_train[df_train["stock_code"] == sc].sort_values("week_start")
        y_train_map[sc] = g["units_sold"].to_numpy(dtype=float)
    return y_train_map


def _ensure_str_stock_code(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte stock_code a str para evitar problemas con category y .map()."""
    df = df.copy()
    if "stock_code" in df.columns:
        df["stock_code"] = df["stock_code"].astype(str)
    return df


def run_backtesting(
    n_splits: int = 8,
    horizon: int = 4,
    save_predictions: bool = True,
    objective: str = "regression_l1",     # ← NUEVO
    metric: str = "mae",                  # ← NUEVO
    predictions_path: Path | None = None, # ← NUEVO (para no sobreescribir)
) -> pd.DataFrame:
    """
    Ejecuta el backtesting completo.

    Parámetros
    ----------
    n_splits : número de cortes.
    horizon : horizonte de predicción (semanas).
    save_predictions : si True, guarda backtest_predictions.parquet.
    objective : objective de LightGBM ('regression_l1', 'regression', ...).
    metric : métrica de evaluación.
    predictions_path : ruta alternativa para guardar predicciones
                       (útil para comparar objectives sin sobreescribir).
    """
    logger.info("Cargando serie semanal...")
    df = load_forecastable_series()
    logger.info(f"  {len(df):,} observaciones, {df['stock_code'].nunique()} productos")

    weeks = sorted(df["week_start"].dt.date.unique().tolist())
    splits = rolling_origin_splits(weeks, horizon=horizon, n_splits=n_splits)
    logger.info(f"Generados {len(splits)} cortes de backtesting")

    all_metrics: list[pd.DataFrame] = []
    all_predictions: list[pd.DataFrame] = []

    for i, split in enumerate(splits, start=1):
        logger.info(f"\n=== Corte {i}/{len(splits)}: cutoff = {split.cutoff} ===")

        cutoff_ts = pd.Timestamp(split.cutoff)
        test_start_ts = pd.Timestamp(split.test_start)
        test_end_ts = pd.Timestamp(split.test_end)

        # 1. Features
        features, y_true = build_features(df, cutoff=split.cutoff, horizon=horizon)
        if features.empty:
            logger.warning(f"  Corte {i} sin features, saltando.")
            continue
        features_df = features.assign(y_true=y_true).reset_index(drop=True)
        features_df = _ensure_str_stock_code(features_df)

        # 2. Split train/valid (80/20 temporal)
        unique_weeks = sorted(features_df["week_start"].unique())
        cutoff_week_valid = unique_weeks[int(len(unique_weeks) * 0.8)]
        train_mask = features_df["week_start"] < cutoff_week_valid
        valid_mask = features_df["week_start"] >= cutoff_week_valid

        # 3. Entrenar LightGBM (parametrizado)
        model = train_lightgbm(
            train_df=features_df[train_mask],
            valid_df=features_df[valid_mask],
            objective=objective,
            metric=metric,
        )

        # 4. Predecir con LightGBM
        lgb_preds = predict_lightgbm(model, features_df)
        lgb_preds = _ensure_str_stock_code(lgb_preds)
        lgb_preds = lgb_preds[
            (lgb_preds["week_start"] >= test_start_ts)
            & (lgb_preds["week_start"] <= test_end_ts)
        ].dropna(subset=["y_true"])

        # 5. Datos hasta cutoff
        df_train = df[df["week_start"] <= cutoff_ts].copy()
        y_true_map = features_df.set_index(["stock_code", "week_start"])["y_true"]

        # 6. y_train map
        stock_codes_in_test = (
            lgb_preds["stock_code"].unique().tolist()
            if not lgb_preds.empty else []
        )
        y_train_map = _build_y_train_map(df_train, stock_codes_in_test)

        # 7. Evaluar LightGBM
        if not lgb_preds.empty:
            lgb_preds = lgb_preds.copy()
            lgb_preds["y_train"] = lgb_preds["stock_code"].map(y_train_map)
            lgb_preds = lgb_preds.dropna(subset=["y_train"]).reset_index(drop=True)

        if not lgb_preds.empty:
            lgb_metrics = evaluate_forecast(
                lgb_preds,
                y_true_col="y_true",
                y_train_col="y_train",
                group_cols=["stock_code"],
                seasonality=52,
            )
            lgb_metrics["model"] = f"lightgbm_{objective}"   # ← NUEVO: distinguir objectives
            lgb_metrics["split_id"] = i
            lgb_metrics["cutoff"] = split.cutoff
            all_metrics.append(lgb_metrics)

            if save_predictions:
                preds_to_save = lgb_preds[["stock_code", "week_start", "y_true", "y_pred"]].copy()
                preds_to_save["model"] = f"lightgbm_{objective}"   # ← NUEVO
                preds_to_save["split_id"] = i
                all_predictions.append(preds_to_save)
        else:
            logger.warning(f"  LightGBM sin predicciones válidas para corte {i}")

        # 8. Baselines (solo una vez, sin duplicar por objective)
        #    Si objective != "regression_l1", no repetimos baselines.
        if objective == "regression_l1":
            baselines = {
                "mean": mean_forecast,
                "naive": naive_forecast,
                "seasonal_naive": seasonal_naive_forecast,
                "moving_average": moving_average_forecast,
                "drift": drift_forecast,
            }

            for name, func in baselines.items():
                try:
                    preds = func(df_train, horizon=horizon)
                    preds = _ensure_str_stock_code(preds)
                    preds["week_start"] = pd.to_datetime(preds["week_start"])
                    preds = preds[
                        (preds["week_start"] >= test_start_ts)
                        & (preds["week_start"] <= test_end_ts)
                    ]
                    if preds.empty:
                        continue
                    preds = preds.copy()
                    preds["y_true"] = preds.set_index(
                        ["stock_code", "week_start"]
                    ).index.map(y_true_map)
                    preds = preds.dropna(subset=["y_true"])
                    if preds.empty:
                        continue
                    preds["y_train"] = preds["stock_code"].map(y_train_map)
                    preds = preds.dropna(subset=["y_train"]).reset_index(drop=True)
                    if preds.empty:
                        continue

                    m = evaluate_forecast(
                        preds,
                        y_true_col="y_true",
                        y_train_col="y_train",
                        group_cols=["stock_code"],
                        seasonality=52,
                    )
                    m["model"] = name
                    m["split_id"] = i
                    m["cutoff"] = split.cutoff
                    all_metrics.append(m)

                    if save_predictions:
                        preds_to_save = preds[["stock_code", "week_start", "y_true", "y_pred"]].copy()
                        preds_to_save["model"] = name
                        preds_to_save["split_id"] = i
                        all_predictions.append(preds_to_save)
                except Exception as e:
                    logger.warning(f"  Baseline {name} falló: {e}")

    # Guardar predicciones (ruta parametrizable)
    if save_predictions and all_predictions:
        preds_df = pd.concat(all_predictions, ignore_index=True)
        if predictions_path is None:
            predictions_path = ROOT_DIR / "data" / "processed" / f"backtest_predictions_{objective}.parquet"
        preds_df.to_parquet(predictions_path, index=False)
        logger.info(f"Predicciones guardadas: {predictions_path} ({len(preds_df):,} filas)")

    if not all_metrics:
        raise RuntimeError("Ningún modelo generó métricas")

    return pd.concat(all_metrics, ignore_index=True)


def aggregate_results(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega métricas por modelo (MASE solo si existe)."""
    agg_dict = {
        "mae_mean": ("mae", "mean"),
        "mae_median": ("mae", "median"),
        "wape_mean": ("wape", "mean"),
        "wape_median": ("wape", "median"),
        "bias_mean": ("bias", "mean"),
        "n_groups": ("stock_code", "count"),
    }
    if "mase" in df.columns:
        agg_dict["mase_mean"] = ("mase", "mean")
        agg_dict["mase_median"] = ("mase", "median")

    return (
        df.groupby("model")
        .agg(**agg_dict)
        .round(4)
        .sort_values("wape_mean")
    )


if __name__ == "__main__":
    metrics_df = run_backtesting(n_splits=8, horizon=4)
    agg = aggregate_results(metrics_df)
    print("\n=== Resumen por modelo ===")
    print(agg.to_string())
"""
Módulo D.3 — Modelo LightGBM global.

Un único modelo para todos los productos y horizontes.
`stock_code` y `week_of_year` son features categóricas.

Permite parametrizar el `objective` y `metric` para experimentar con
regression_l1, regression, poisson o tweedie.
"""

from __future__ import annotations

import logging

import lightgbm as lgb
import numpy as np
import pandas as pd

from src.models.features import CATEGORICAL_COLS, FEATURE_COLS

logger = logging.getLogger(__name__)


def prepare_for_lightgbm(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara el DataFrame:
        - Codifica categóricas como 'category'.
        - Mantiene NaN en lags (LightGBM los maneja nativamente).
    """
    df = df.copy()
    for c in CATEGORICAL_COLS:
        if c in df.columns:
            df[c] = df[c].astype("category")
    return df


def train_lightgbm(
    train_df: pd.DataFrame,
    valid_df: pd.DataFrame | None = None,
    n_estimators: int = 500,
    learning_rate: float = 0.05,
    num_leaves: int = 31,
    min_child_samples: int = 20,
    random_state: int = 42,
    objective: str = "regression_l1",     # ← NUEVO
    metric: str = "mae",                  # ← NUEVO
    tweedie_variance_power: float = 1.5,  # ← NUEVO (solo tweedie)
) -> lgb.LGBMRegressor:
    """
    Entrena un LGBMRegressor global.

    Parámetros
    ----------
    train_df : DataFrame con features + y_true.
    valid_df : opcional, para early stopping.
    n_estimators : número máximo de árboles.
    learning_rate : tasa de aprendizaje.
    num_leaves : hojas por árbol.
    min_child_samples : mínimo de muestras por hoja (regularización).
    random_state : semilla.
    objective : función de pérdida de LightGBM
                ('regression_l1').
    metric : métrica de evaluación (debe coincidir con objective).
             'mae' para l1 para regression' para los otros.
    tweedie_variance_power : solo para objective='tweedie'.

    Devuelve
    --------
    Modelo LightGBM entrenado.
    """
    # 1. Validar y limpiar train
    if "y_true" not in train_df.columns:
        raise ValueError("train_df debe tener columna 'y_true'")

    train_df = train_df.dropna(subset=["y_true"]).reset_index(drop=True)
    if train_df.empty:
        raise ValueError("train_df está vacío después de dropna(y_true)")

    missing = set(FEATURE_COLS) - set(train_df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en train_df: {missing}")

    train_df = prepare_for_lightgbm(train_df)
    X_train = train_df[FEATURE_COLS]
    y_train = train_df["y_true"].to_numpy(dtype=float)

    # 2. Crear modelo (parametrizado)
    params = {
        "objective": objective,
        "metric": metric,
        "n_estimators": n_estimators,
        "learning_rate": learning_rate,
        "num_leaves": num_leaves,
        "min_child_samples": min_child_samples,
        "random_state": random_state,
        "verbose": -1,
    }
    if objective == "tweedie":
        params["tweedie_variance_power"] = tweedie_variance_power

    model = lgb.LGBMRegressor(**params)

    # 3. Preparar validación
    fit_kwargs = {}
    if valid_df is not None and not valid_df.empty:
        if "y_true" not in valid_df.columns:
            raise ValueError("valid_df debe tener columna 'y_true'")
        valid_df = valid_df.dropna(subset=["y_true"]).reset_index(drop=True)
        missing = set(FEATURE_COLS) - set(valid_df.columns)
        if missing:
            raise ValueError(f"Faltan columnas en valid_df: {missing}")
        valid_df = prepare_for_lightgbm(valid_df)
        X_valid = valid_df[FEATURE_COLS]
        y_valid = valid_df["y_true"].to_numpy(dtype=float)
        fit_kwargs["eval_set"] = [(X_valid, y_valid)]
        fit_kwargs["callbacks"] = [lgb.early_stopping(50, verbose=False)]

    # 4. Entrenar
    model.fit(X_train, y_train, **fit_kwargs)

    # 5. Loguear métricas de validación
    if valid_df is not None:
        best_iter = getattr(model, "best_iteration_", None)
        if best_iter is not None:
            logger.info("Best iteration: %d", best_iter)
        try:
            logger.info("Best %s (valid): %.4f", metric, model.best_score_["valid_0"][metric])
        except (KeyError, AttributeError):
            pass

    return model


def predict_lightgbm(model: lgb.LGBMRegressor, df: pd.DataFrame) -> pd.DataFrame:
    """
    Genera predicciones para un DataFrame con features.

    Funciona con o sin columna 'y_true' (útil para predecir futuro).

    Devuelve
    --------
    DataFrame con [stock_code, week_start, horizon, (y_true), y_pred].
    """
    missing = set(FEATURE_COLS) - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en df: {missing}")

    df = prepare_for_lightgbm(df)
    X = df[FEATURE_COLS]
    preds = np.clip(model.predict(X), 0, None)

    base_cols = ["stock_code", "week_start", "horizon"]
    out = df[base_cols].copy()
    if "y_true" in df.columns:
        out["y_true"] = df["y_true"]
    out["y_pred"] = preds
    return out
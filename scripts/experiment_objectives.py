"""Experimento rápido de objectives de LightGBM."""

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

from src.models.features import FEATURE_COLS
from src.models.lightgbm_model import prepare_for_lightgbm
from src.models.pipeline import load_forecastable_series
from src.models.features import build_features

# 1. Cargar datos
df = load_forecastable_series()
cutoff = pd.Timestamp("2011-07-11").date()
features, y_true = build_features(df, cutoff=cutoff, horizon=4)
features_df = features.assign(y_true=y_true).reset_index(drop=True)

# 2. Split temporal 80/20
weeks = sorted(features_df["week_start"].unique())
cut_week = weeks[int(len(weeks) * 0.8)]
train = features_df[features_df["week_start"] < cut_week].copy()
valid = features_df[features_df["week_start"] >= cut_week].copy()

# 3. Preparar categóricas (unificadas entre train y valid)
train = prepare_for_lightgbm(train)
valid = prepare_for_lightgbm(valid)

# 4. Features y target
X_train = train[FEATURE_COLS]
y_train = train["y_true"].values
X_valid = valid[FEATURE_COLS]
y_valid = valid["y_true"].values

# 5. Experimentos
OBJECTIVES = {
    "regression": "l2",
    "regression_l1": "l1",
    "poisson": "poisson",
    "tweedie": "tweedie",
}

print(f"{'objective':20s} {'MAE':>8s} {'bias':>8s} {'best_iter':>10s}")
print("-" * 50)

for objective, metric in OBJECTIVES.items():
    model = lgb.LGBMRegressor(
        objective=objective,
        metric=metric,
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        verbose=-1,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_valid, y_valid)],
        callbacks=[lgb.early_stopping(50, verbose=False)],
    )
    preds = np.clip(model.predict(X_valid), 0, None)
    mae = mean_absolute_error(y_valid, preds)
    bias = np.mean(preds - y_valid)
    best_iter = model.best_iteration_ if hasattr(model, "best_iteration_") else "N/A"
    print(f"{objective:20s} {mae:8.2f} {bias:+8.2f} {best_iter:>10}")
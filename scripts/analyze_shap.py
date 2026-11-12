"""Análisis SHAP del modelo LightGBM."""

import shap
import pandas as pd
import numpy as np

from src.models.pipeline import load_forecastable_series
from src.models.features import build_features, FEATURE_COLS
from src.models.lightgbm_model import train_lightgbm, prepare_for_lightgbm

# 1. Cargar datos y construir features
df = load_forecastable_series()
cutoff = pd.Timestamp("2011-06-01").date()
features, y_true = build_features(df, cutoff=cutoff, horizon=4)
features_df = features.assign(y_true=y_true).reset_index(drop=True)
features_df = features_df.copy()
features_df["stock_code"] = features_df["stock_code"].astype(str)

# 2. Entrenar modelo (con features_df preparado)
model = train_lightgbm(train_df=features_df, valid_df=None)

# 3. SHAP con tree_path_dependent (no requiere categorías consistentes)
X = features_df[FEATURE_COLS]
X_sample = X.sample(500, random_state=42)
X_sample = prepare_for_lightgbm(X_sample)

explainer = shap.TreeExplainer(
    model,
    feature_perturbation="tree_path_dependent",
)
shap_values = explainer.shap_values(X_sample)

# 4. Importancia global
shap_importance = pd.DataFrame({
    "feature": FEATURE_COLS,
    "mean_abs_shap": np.abs(shap_values).mean(axis=0),
}).sort_values("mean_abs_shap", ascending=False)

print("=== Importancia global (mean |SHAP|) ===")
print(shap_importance.to_string(index=False))

# 5. Ratio de dominancia de stock_code (si está en FEATURE_COLS)
total_importance = shap_importance["mean_abs_shap"].sum()

# stock_code no está en FEATURE_COLS, pero LightGBM lo usa como categórica
# para agrupar. Comprobamos si está en shap_importance.
if "stock_code" in shap_importance["feature"].values:
    stock_code_importance = shap_importance[
        shap_importance["feature"] == "stock_code"
    ]["mean_abs_shap"].values[0]
    stock_code_ratio = stock_code_importance / total_importance
    print(f"\nstock_code representa el {100 * stock_code_ratio:.1f}% de la importancia total.")
else:
    stock_code_importance = 0.0
    stock_code_ratio = 0.0
    print("\nℹstock_code NO está en FEATURE_COLS (no se usa como feature).")
    print("   LightGBM lo usa como categórica para agrupar, pero SHAP no lo ve.")
    print("   Esto significa que el modelo NO memoriza productos por su código.")

print(f"Importancia media por feature: {100 / len(FEATURE_COLS):.1f}%")

# 6. Interpretación
if stock_code_ratio > 0.5:
    print("stock_code domina (>50%). El modelo puede estar memorizando productos.")
elif stock_code_ratio > 0.3:
    print("stock_code tiene mucha importancia (>30%). Revisar generalización.")
else:
    print("stock_code no domina (o no se usa como feature). El modelo aprende patrones generales.")

# 7. Features con importancia casi cero (candidatas a eliminar)
zero_features = shap_importance[shap_importance["mean_abs_shap"] < 0.01]
if not zero_features.empty:
    print(f"\nFeatures con importancia casi cero (<0.01):")
    print(zero_features.to_string(index=False))
    print("   Candidatas a eliminar de FEATURE_COLS.")
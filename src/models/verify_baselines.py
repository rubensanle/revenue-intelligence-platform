"""Prueba integrada de baselines con datos reales."""
import duckdb
from src.models.backtest import rolling_origin_splits
from src.models.baselines import (
    naive_forecast, seasonal_naive_forecast, moving_average_forecast,
    mean_forecast, drift_forecast,
)

con = duckdb.connect("data/processed/revenue.duckdb", read_only=True)
df = con.execute("""
    SELECT w.stock_code, w.week_start, w.units_sold
    FROM v_weekly_sales w
    JOIN v_forecastable_products f USING (stock_code)
    WHERE f.forecastability = 'forecastable'
    ORDER BY w.stock_code, w.week_start
""").df()
con.close()

print("Semanas únicas:", df["week_start"].nunique())
print("Productos forecastable:", df["stock_code"].nunique())
print("Observaciones:", len(df))
print()

# Ejemplo para un producto conocido
product = "84077"
sub = df[df["stock_code"] == product].copy()
if sub.empty:
    print(f"Producto {product} no encontrado. Usando el primero disponible.")
    product = df["stock_code"].iloc[0]
    sub = df[df["stock_code"] == product].copy()

print(f"Ejemplo de predicciones para el producto {product}:")
print("Últimas 5 semanas reales:")
print(sub.tail(5)[["week_start", "units_sold"]].to_string(index=False))
print()

print("Naive:")
print(naive_forecast(sub, horizon=4).to_string(index=False))
print()

print("Seasonal naive:")
print(seasonal_naive_forecast(sub, horizon=4, seasonality=52).to_string(index=False))
print()

print("Moving average (window=4):")
print(moving_average_forecast(sub, window=4, horizon=4).to_string(index=False))
print()

print("Mean:")
print(mean_forecast(sub, horizon=4).to_string(index=False))
print()

print("Drift:")
print(drift_forecast(sub, horizon=4).to_string(index=False))
print()

# Prueba de splits
print("=== Backtesting splits ===")
week_starts = sub["week_start"].tolist()
try:
    splits = rolling_origin_splits(week_starts, horizon=4, n_splits=3)
    for s in splits:
        print(f"  Cutoff: {s.cutoff}, Test: {s.test_start} → {s.test_end}")
except ValueError as e:
    print(f"⚠️ No se pudieron generar splits: {e}")
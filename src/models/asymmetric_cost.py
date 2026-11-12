# src/models/asymmetric_cost.py
"""Coste asimétrico de errores de forecasting."""

import numpy as np
import pandas as pd

 
def asymmetric_cost(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    unit_stockout_cost: float,
    unit_overstock_cost: float,
) -> float:
    """
    Coste asimétrico total.
    
    unit_stockout_cost: € perdidos por unidad infra-predicha (rotura).
    unit_overstock_cost: € perdidos por unidad sobre-predicha (exceso).
    """
    errors = y_true - y_pred  # positivo = infra-predice, negativo = sobre-predice
    
    # Infra-predicción (rotura): error > 0
    stockout_units = np.maximum(0, errors)
    stockout_cost = stockout_units * unit_stockout_cost
    
    # Sobre-predicción (exceso): error < 0
    overstock_units = np.maximum(0, -errors)
    overstock_cost = overstock_units * unit_overstock_cost
    
    return float(np.sum(stockout_cost + overstock_cost))


def cost_per_unit(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    unit_stockout_cost: float,
    unit_overstock_cost: float,
) -> float:
    """Coste medio por unidad vendida."""
    total_units = np.sum(np.abs(y_true))
    if total_units == 0:
        return np.nan
    return asymmetric_cost(y_true, y_pred, unit_stockout_cost, unit_overstock_cost) / total_units
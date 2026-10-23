"""
Módulo D.2 — Rolling-origin backtesting.

Divide la serie temporal en múltiples cortes y entrena/evalúa
el modelo avanzando el corte 4 semanas cada vez.

Esquema:
    Corte 1: train [inicio .. T1], test [T1+1 .. T1+horizon]
    Corte 2: train [inicio .. T2], test [T2+1 .. T2+horizon]
    ...
    Corte N: train [inicio .. TN], test [TN+1 .. TN+horizon]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BacktestSplit:
    """Un único corte de backtesting."""
    cutoff: date
    train_start: date
    train_end: date
    test_start: date
    test_end: date


def rolling_origin_splits(
    week_starts: list[date],
    horizon: int = 4,
    n_splits: int = 8,
    step: int | None = None,
) -> list[BacktestSplit]:
    """
    Genera n_splits cortes de backtesting avanzando en el tiempo.

    Parámetros
    ----------
    week_starts : lista ordenada de todas las semanas disponibles.
    horizon : semanas a predecir en cada corte.
    n_splits : número de cortes.
    step : semanas entre cortes. Por defecto = horizon (no solapar).

    Devuelve
    --------
    Lista de BacktestSplit, del más antiguo al más reciente.
    """
    week_starts = sorted(set(pd.to_datetime(week_starts).date))
    if step is None:
        step = horizon

    if len(week_starts) < horizon * (n_splits + 1):
        raise ValueError(
            f"No hay suficientes semanas: {len(week_starts)} < "
            f"{horizon * (n_splits + 1)}"
        )

    splits: list[BacktestSplit] = []
    # Último test posible: las últimas 'horizon' semanas
    last_test_end_idx = len(week_starts) - 1

    for k in range(n_splits):
        test_end_idx = last_test_end_idx - k * step
        test_start_idx = test_end_idx - horizon + 1
        train_end_idx = test_start_idx - 1
        if train_end_idx < 52:
            raise ValueError(
                f"Corte {k}: train tiene solo {train_end_idx + 1} semanas, "
                "se necesitan al menos 53 para seasonal naive"
            )
        splits.append(BacktestSplit(
            cutoff=week_starts[train_end_idx],
            train_start=week_starts[0],
            train_end=week_starts[train_end_idx],
            test_start=week_starts[test_start_idx],
            test_end=week_starts[test_end_idx],
        ))

    return sorted(splits, key=lambda s: s.cutoff)
"""
Módulo A.1 — Ingesta del dataset original.

Responsabilidad:
    - Localizar el CSV en data/raw/
    - Calcular su hash SHA-256 (reproducibilidad)
    - Cargarlo en pandas sin modificarlo
    - Registrarlo en DuckDB como tabla 'raw_transactions'

Principio: NO se modifica nada en este paso. Solo se lee y se registra.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import duckdb
import pandas as pd

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

# Rutas (relativas a la raíz del repo)
ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
DB_PATH = ROOT_DIR / "data" / "processed" / "revenue.duckdb"

# Nombres esperados
RAW_TABLE = "raw_transactions"
CSV_GLOB = "*.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Funciones
# ---------------------------------------------------------------------------

def find_raw_csv() -> Path:
    """Localiza el CSV en data/raw/. Falla si hay 0 o más de 1."""
    candidates = list(RAW_DIR.glob(CSV_GLOB))
    if not candidates:
        raise FileNotFoundError(
            f"No se encontró ningún CSV en {RAW_DIR}. "
            "Coloca el dataset de Online Retail II ahí."
        )
    if len(candidates) > 1:
        raise RuntimeError(
            f"Se encontraron varios CSV en {RAW_DIR}: {candidates}. "
            "Deja solo uno para garantizar reproducibilidad."
        )
    return candidates[0]


def compute_sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    """Calcula el SHA-256 del fichero en streaming (no lo carga entero en RAM)."""
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha.update(chunk)
    return sha.hexdigest()


def load_csv(path: Path) -> pd.DataFrame:
    """
    Carga el CSV con pandas.

    Notas sobre el dataset Online Retail II:
        - El fichero tiene DOS hojas en Excel, pero la versión CSV suele ser
          la combinación de ambas. Si tu CSV viene de una sola hoja, ajusta.
        - Encoding habitual: 'utf-8' o 'latin-1'. Probamos utf-8 y fallback.
    """
    try:
        df = pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        logger.warning("UTF-8 falló, probando latin-1...")
        df = pd.read_csv(path, encoding="latin-1")
    return df


def register_in_duckdb(df: pd.DataFrame, db_path: Path, table: str) -> None:
    """Registra el DataFrame como tabla en DuckDB, reemplazando si existe."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        con.execute(f"DROP TABLE IF EXISTS {table}")
        con.register("df_view", df)
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM df_view")
        con.unregister("df_view")
        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        logger.info(f"Tabla '{table}' registrada en DuckDB con {n:,} filas.")
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("=== Iniciando ingesta del dataset original ===")

    csv_path = find_raw_csv()
    logger.info(f"CSV encontrado: {csv_path.name}")

    sha = compute_sha256(csv_path)
    logger.info(f"SHA-256: {sha}")
    logger.info(f"Tamaño: {csv_path.stat().st_size / 1e6:.2f} MB")

    df = load_csv(csv_path)
    logger.info(f"Shape: {df.shape[0]:,} filas × {df.shape[1]} columnas")
    logger.info(f"Columnas: {list(df.columns)}")
    logger.info(f"Memoria: {df.memory_usage(deep=True).sum() / 1e6:.2f} MB")

    logger.info("\nPrimeras 5 filas:")
    logger.info("\n" + df.head().to_string())

    logger.info("\nTipos de datos:")
    logger.info("\n" + df.dtypes.to_string())

    register_in_duckdb(df, DB_PATH, RAW_TABLE)

    logger.info(f"\n=== Ingesta completada. Base de datos: {DB_PATH} ===")


if __name__ == "__main__":
    main()
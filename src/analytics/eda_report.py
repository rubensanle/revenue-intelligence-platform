"""
Módulo C — Genera el informe de EDA en Markdown con figuras.

Produce:
    - docs/eda_report.md
    - docs/figures/*.png (o .html si prefieres interactivo)

Cada sección responde a una de las 5 preguntas con métricas cuantificadas.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.analytics.diagnostics import (
    q1_monthly_evolution,
    q1_seasonality_by_dow,
    q2_concentration_curve,
    q2_product_trend,
    q2_top_bottom_products,
    q3_repeat_purchase_rate,
    q3_rfm_distribution,
    q4_country_ranking,
    q5_forecastability,
    q6_returns_by_product,
    q6_returns_by_customer
)

ROOT_DIR = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT_DIR / "docs"
FIGURES_DIR = DOCS_DIR / "figures"
REPORT_PATH = DOCS_DIR / "eda_report.md"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def save_fig(fig: go.Figure, name: str) -> str:
    """Guarda una figura y devuelve la ruta relativa para el Markdown."""
    path = FIGURES_DIR / f"{name}.html"
    fig.write_html(path, include_plotlyjs="cdn")
    return f"figures/{name}.html"


def df_to_md(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df.empty:
        return "_Sin resultados._\n"
    return df.head(max_rows).to_markdown(index=False) + "\n"


def section_1_evolution() -> str:
    """Pregunta 1: ¿Cómo evoluciona el negocio?"""
    df = q1_monthly_evolution()
    dow = q1_seasonality_by_dow()

    # Gráfico mensual
    fig = px.line(
        df, x="month", y="net_revenue",
        title="Ingresos netos por mes",
        labels={"month": "Mes", "net_revenue": "Ingresos netos (£)"},
        markers=True,
    )
    fig_path = save_fig(fig, "q1_monthly_revenue")

    total = df["net_revenue"].sum()
    n_months = len(df)
    avg = total / n_months
    best = df.loc[df["net_revenue"].idxmax()]
    worst = df.loc[df["net_revenue"].idxmin()]

    out = "## Pregunta 1 — ¿Cómo evoluciona el negocio?\n\n"
    out += f"- **Meses analizados:** {n_months} (excluye dic-2011, parcial)\n"
    out += f"- **Ingreso neto total:** £{total:,.2f}\n"
    out += f"- **Ingreso medio mensual:** £{avg:,.2f}\n"
    out += f"- **Mejor mes:** {best['month'].date()} con £{best['net_revenue']:,.2f}\n"
    out += f"- **Peor mes:** {worst['month'].date()} con £{worst['net_revenue']:,.2f}\n"
    out += f"\n[Ver gráfico interactivo]({fig_path})\n\n"
    out += "**Meses con mayor ingreso:**\n\n"
    out += df_to_md(df.nlargest(5, "net_revenue")[["month", "net_revenue", "units_sold"]])
    out += "\n**Estacionalidad por día de la semana:**\n\n"
    out += df_to_md(dow[["day_name", "avg_revenue", "n_days"]])
    out += "\n**Hallazgo de negocio:** el minorista prácticamente no opera los sábados "
    out += "(solo 1 día con ventas en 2 años) y los domingos tiene ventas online "
    out += "residuales. El negocio es fundamentalmente de lunes a viernes.\n\n"
    out += "**Implicación para forecasting:** la agregación semanal ya captura esto; "
    out += "no usaremos `day_of_week` como feature porque el nivel de señal es semanal.\n"
    return out


def section_2_products() -> str:
    """Pregunta 2: ¿Qué productos generan el valor?"""
    conc = q2_concentration_curve()
    top_bottom = q2_top_bottom_products(20)
    trend = q2_product_trend()

    # ¿Cuántos productos generan el 80% del ingreso?
    row_80 = conc[conc["pct_revenue"] >= 80.0].iloc[0] if not conc.empty else None
    n_80 = int(row_80["rank"]) if row_80 is not None else 0
    pct_80 = float(row_80["pct_products"]) if row_80 is not None else 0.0

    # Gráfico de concentración
    fig = px.line(
        conc, x="pct_products", y="pct_revenue",
        title="Curva de concentración de ingresos por producto",
        labels={"pct_products": "% acumulado de productos",
                "pct_revenue": "% acumulado de ingresos"},
    )
    fig.add_hline(y=80, line_dash="dash", line_color="red",
                  annotation_text="80% de ingresos")
    fig_path = save_fig(fig, "q2_concentration")

    # Separar por tipo de tendencia
    trend_counts = trend["trend"].value_counts().reset_index()
    trend_counts.columns = ["trend", "n_products"]

    growing   = trend[trend["trend"] == "growing"]
    declining = trend[trend["trend"] == "declining"]
    new_launch = trend[trend["trend"] == "new_launch"]
    dormant    = trend[trend["trend"] == "dormant"]
    anomalies  = trend[trend["trend"] == "anomaly_returns"]

    out = "## Pregunta 2 — ¿Qué productos generan el valor?\n\n"
    out += "### Concentración\n\n"
    out += f"- **{n_80} productos** ({pct_80:.2f}% del catálogo) generan el **80% del ingreso**.\n"
    out += f"- Total de productos con ingresos positivos: {len(conc)}\n"
    out += f"\n[Ver gráfico interactivo]({fig_path})\n\n"

    out += "### Clasificación de tendencias\n\n"
    out += df_to_md(trend_counts)

    # Top crecimiento (solo base comparable)
    out += "\n**Top 10 productos en crecimiento (base comparable):**\n\n"
    out += df_to_md(
        growing.nlargest(10, "delta")[
            ["stock_code", "units_recent", "units_previous", "delta", "growth_pct"]
        ]
    )

    # Top declive (solo declives reales)
    out += "\n**Top 10 productos en declive (reales):**\n\n"
    out += df_to_md(
        declining.nsmallest(10, "delta")[
            ["stock_code", "units_recent", "units_previous", "delta", "growth_pct"]
        ]
    )

    # Productos nuevos
    if not new_launch.empty:
        out += f"\n### Productos nuevos ({len(new_launch)})\n\n"
        out += "Lanzados después de feb-2011. **No tienen `growth_pct`** "
        out += "(no hay base comparable). Se evalúan por métricas absolutas: "
        out += "`units_per_month`, `n_invoices`, `avg_units_per_invoice`.\n\n"
        out += df_to_md(
            new_launch.nlargest(10, "units_recent")[
                ["stock_code", "first_sale_date", "units_recent",
                 "units_per_month_recent", "n_invoices_recent",
                 "avg_units_per_invoice"]
            ]
        )

    # Productos dormidos
    if not dormant.empty:
        out += f"\n### Productos dormidos ({len(dormant)})\n\n"
        out += "Existían antes pero no vendieron en el período anterior "
        out += "(estacionalidad, baja rotación, o pausa). **No tienen `growth_pct`.**\n\n"
        out += df_to_md(
            dormant.nlargest(10, "units_recent")[
                ["stock_code", "first_sale_date", "units_recent",
                 "units_per_month_recent", "n_invoices_recent"]
            ]
        )

    wholesale = trend[trend["trend"] == "wholesale_dependent"]

    if not wholesale.empty:
        out += f"\n### Productos dependientes de mayoristas ({len(wholesale)})\n\n"
        out += "Productos con **alguna línea > 10.000 unidades**. "
        out += "Su `growth_pct` no se calcula porque un solo pedido mayorista "
        out += "distorsiona la serie. Se muestran métricas absolutas.\n\n"
        out += df_to_md(
            wholesale.nlargest(10, "units_recent")[
                ["stock_code", "units_recent", "units_previous",
                "units_per_month_recent", "n_invoices_recent"]
            ]
        )

    # Anomalías
    if not anomalies.empty:
        out += f"\n### Anomalías de devoluciones ({len(anomalies)})\n\n"
        out += "Productos con **tasa de devolución > 50%** en el período reciente "
        out += "o con **devoluciones masivas históricas** (`units_previous < 0`). "
        out += "Puede ser devolución de ventas anteriores, ajuste de inventario o error.\n\n"
        out += df_to_md(
            anomalies.nsmallest(10, "delta")[
                ["stock_code", "units_recent", "units_previous", "delta",
                "return_rate_recent_pct"]
            ]
        )

    # Top 10 por ingreso
    out += "\n### Top 10 productos por ingreso\n\n"
    out += df_to_md(
        top_bottom["top"].head(10)[
            ["stock_code", "description", "net_revenue", "units_sold"]
        ]
    )
    return out

def section_3_customers() -> str:
    """Pregunta 3: ¿Qué patrones presentan los clientes?"""
    rfm = q3_rfm_distribution()
    repeat = q3_repeat_purchase_rate()

    fig = px.bar(
        rfm, x="rfm_segment", y="n_customers",
        title="Distribución de clientes por segmento RFM",
        labels={"rfm_segment": "Segmento", "n_customers": "Nº de clientes"},
    )
    fig_path = save_fig(fig, "q3_rfm")

    out = "## Pregunta 3 — ¿Qué patrones presentan los clientes?\n\n"
    out += f"- **Clientes identificados totales:** {repeat['total_customers']:,}\n"
    out += f"- **Clientes recurrentes (más de 1 factura):** {repeat['repeat_customers']:,} "
    out += f"({repeat['repeat_rate_pct']:.2f}%)\n"
    out += f"- **Frecuencia media de compra:** {repeat['avg_frequency']:.2f} facturas/cliente\n"
    out += f"\n[Ver gráfico interactivo]({fig_path})\n\n"
    out += "**Distribución por segmento RFM:**\n\n"
    out += df_to_md(rfm)
    return out


def section_4_markets() -> str:
    """Pregunta 4: ¿Qué mercados son más importantes?"""
    df = q4_country_ranking()
    uk = df[df["country"] == "United Kingdom"]
    non_uk = df[df["country"] != "United Kingdom"]

    fig = px.bar(
        non_uk.head(15), x="country", y="net_revenue",
        title="Top 15 mercados fuera del Reino Unido por ingreso",
        labels={"country": "País", "net_revenue": "Ingresos netos (£)"},
    )
    fig_path = save_fig(fig, "q4_markets")

    uk_pct = float(uk["pct_revenue"].iloc[0]) if not uk.empty else 0.0

    out = "## Pregunta 4 — ¿Qué mercados son más importantes?\n\n"
    out += f"- **Reino Unido:** {uk_pct:.2f}% del ingreso total.\n"
    out += f"- **Total de países:** {len(df)}\n"
    out += f"\n[Ver gráfico interactivo]({fig_path})\n\n"
    out += "**Top 10 países fuera del Reino Unido:**\n\n"
    out += df_to_md(non_uk.head(10)[["country", "net_revenue", "units_sold", "n_customers", "pct_revenue"]])
    return out


def section_5_forecastability() -> str:
    """Pregunta 5: ¿Qué productos se pueden prever con fiabilidad?"""
    df = q5_forecastability()

    counts = df["forecastability"].value_counts().reset_index()
    counts.columns = ["forecastability", "n_products"]

    fig = px.pie(
        counts, names="forecastability", values="n_products",
        title="Clasificación de productos por forecastability",
    )
    fig_path = save_fig(fig, "q5_forecastability")

    out = "## Pregunta 5 — ¿Qué productos se pueden prever con fiabilidad?\n\n"
    out += f"Total de productos: {len(df):,}\n\n"
    out += df_to_md(counts)
    out += f"\n[Ver gráfico interactivo]({fig_path})\n\n"

    out += "**Interpretación:**\n\n"
    out += "- `forecastable`: productos con volumen razonable y estacionalidad estable. "
    out += "Candidatos a forecasting individual.\n"
    out += "- `intermittent`: más del 50% de semanas sin venta. Requieren modelos "
    out += "agregados o métodos específicos para demanda intermitente (Croston).\n"
    out += "- `high_variance`: CV > 1.5. Predicción individual muy ruidosa.\n"
    out += "- `low_volume`: < 50 unidades totales. No merece la pena predecir individualmente.\n\n"

    out += "**Ejemplos de productos forecastable (top 10 por volumen):**\n\n"
    out += df_to_md(
        df[df["forecastability"] == "forecastable"].nlargest(10, "total_units")[
            ["stock_code", "n_active_weeks", "total_units", "mean_weekly_units", "cv"]
        ]
    )
    return out


def section_6_returns() -> str:
    """Pregunta 6: ¿Qué productos y clientes devuelven más?"""
    by_product = q6_returns_by_product()
    by_customer = q6_returns_by_customer()

    high_products = by_product[by_product["return_severity"] == "high_return_rate"]
    high_customers = by_customer[by_customer["returner_severity"] == "high_returner"]

    out = "## Pregunta 6 — ¿Qué productos y clientes devuelven más?\n\n"

    # Productos
    out += "### Devoluciones por producto\n\n"
    out += f"- **Productos con devoluciones:** {len(by_product)}\n"
    out += f"- **Productos con tasa alta (>50%):** {len(high_products)}\n\n"
    out += "**Top 10 productos más devueltos:**\n\n"

    with_sales = by_product[by_product["return_severity"] != "no_sales_but_returns"]
    no_sales = by_product[by_product["return_severity"] == "no_sales_but_returns"]

    out += "**Top 10 productos más devueltos (con ventas):**\n\n"
    out += df_to_md(
        with_sales.head(10)[
            ["stock_code", "description", "units_returned_recent",
             "units_sold_recent", "return_rate_recent_pct", "return_severity"]
        ]
    )

    if not no_sales.empty:
        out += "\n**Productos con devoluciones pero sin ventas (casos especiales):**\n\n"
        out += "Puede ser devolución de ventas anteriores, ajuste de inventario o error. "
        out += "**No tienen `return_rate`** (no se puede calcular sin ventas).\n\n"
        out += df_to_md(
            no_sales.head(5)[
                ["stock_code", "description", "units_returned_recent",
                 "units_sold_recent", "return_severity"]
            ]
        )

    # Clientes
    out += "\n### Devoluciones por cliente\n\n"
    out += f"- **Clientes con devoluciones:** {len(by_customer)}\n"
    out += f"- **Clientes con tasa alta (>30%):** {len(high_customers)}\n\n"
    out += "**Top 10 clientes que más devuelven (unidades):**\n\n"
    out += df_to_md(
        by_customer.head(10)[
            ["customer_id", "country", "units_returned_recent",
             "units_sold_recent", "return_rate_units_pct", "returner_severity"]
        ]
    )

    # Interpretación
    out += "\n**Interpretación:**\n\n"
    out += "- `high_return_rate` (producto): >50% de devoluciones. Producto problemático.\n"
    out += "- `high_returner` (cliente): >30% de devoluciones. Cliente problemático.\n"
    out += "- Los clientes con tasa alta pueden ser devolvedores crónicos o compradores B2B que devuelven stock.\n"
    out += "- Los productos con tasa alta pueden tener problemas de calidad o descripción engañosa.\n"

    return out

def section_7_limitations() -> str:
    """Limitaciones y decisiones de los datos."""
    return (
        "## Limitaciones de los datos\n\n"
        "- **Dataset sin documentación**: Online Retail II es un dataset público "
        "sin información sobre su recolección. Las anomalías pueden ser reales "
        "o errores; no podemos determinarlo.\n"
        "- **Anomalías de devoluciones**: algunos productos tienen más devoluciones "
        "que ventas en ciertos períodos (`anomaly_returns`). Se excluyen del ranking "
        "de declives para no distorsionar el análisis.\n"
        "- **Pedidos mayoristas cancelados**: se usa `units_net_line` "
        "(ventas - cancelaciones - devoluciones) para netear pedidos cancelados.\n"
        "- **Los productos con un porcentaje de growth muy alto, se debe a que en el periodo anterior no se vendieron unidades, "
        "debido a estacionalidad o a nuevas salidas al mercado,lo que resulta en un crecimiento relativo elevado.**\n"
        "- **Pedidos mayoristas puntuales**: productos con líneas > 10.000 unidades "
        "se marcan como `wholesale_dependent y no se calcula su growth_pct`.\n"
        "- **Mes parcial**: diciembre 2011 está incompleto (9 días). "
        "Se excluye de los análisis temporales.\n"
        "- **Sábados**: solo hay 1 día con ventas en sábado en 2 años. "
        "El negocio opera principalmente de lunes a viernes.\n"
    )

def main() -> None:
    logger.info("=== Generando informe EDA ===")

    parts = [
        "# EDA — Online Retail II\n\n",
        "_Generado automáticamente por `src/analytics/eda_report.py`._\n\n",
        "Este informe responde a las **5 preguntas de negocio** del proyecto. "
        "Todas las cifras están calculadas sobre `v_sales_lines` (capa semántica única). "
        "Se excluye diciembre 2011 por estar incompleto.\n\n",
        section_1_evolution(),
        section_2_products(),
        section_3_customers(),
        section_4_markets(),
        section_5_forecastability(),
        section_6_returns(),
        section_7_limitations(),
    ]

    content = "\n".join(parts)
    REPORT_PATH.write_text(content, encoding="utf-8")
    logger.info(f"Informe escrito en {REPORT_PATH}")
    logger.info(f"Tamaño: {len(content):,} caracteres")


if __name__ == "__main__":
    main()
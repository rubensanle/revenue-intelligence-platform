# EDA — Online Retail II


_Generado automáticamente por `src/analytics/eda_report.py`._


Este informe responde a las **5 preguntas de negocio** del proyecto. Todas las cifras están calculadas sobre `v_sales_lines` (capa semántica única). Se excluye diciembre 2011 por estar incompleto.


## Pregunta 1 — ¿Cómo evoluciona el negocio?

- **Meses analizados:** 24 (excluye dic-2011, parcial)
- **Ingreso neto total:** £18,422,814.63
- **Ingreso medio mensual:** £767,617.28
- **Mejor mes:** 2011-11-01 con £1,456,145.80
- **Peor mes:** 2011-04-01 con £492,367.84

[Ver gráfico interactivo](figures/q1_monthly_revenue.html)

**Meses con mayor ingreso:**

| month               |   net_revenue |   units_sold |
|:--------------------|--------------:|-------------:|
| 2011-11-01 00:00:00 |   1.45615e+06 |       768468 |
| 2010-11-01 00:00:00 |   1.4167e+06  |       730417 |
| 2011-10-01 00:00:00 |   1.06937e+06 |       626373 |
| 2010-10-01 00:00:00 |   1.04169e+06 |       622278 |
| 2011-09-01 00:00:00 |   1.0176e+06  |       574169 |

**Estacionalidad por día de la semana:**

| day_name   |   avg_revenue |   n_days |
|:-----------|--------------:|---------:|
| Domingo    |      17904.2  |       98 |
| Lunes      |      34575.8  |       93 |
| Martes     |      35632.9  |      103 |
| Miércoles  |      31101.9  |      103 |
| Jueves     |      37167.7  |      101 |
| Viernes    |      29023    |       97 |
| Sábado     |       9803.05 |        1 |

**Hallazgo de negocio:** el minorista prácticamente no opera los sábados (solo 1 día con ventas en 2 años) y los domingos tiene ventas online residuales. El negocio es fundamentalmente de lunes a viernes.

**Implicación para forecasting:** la agregación semanal ya captura esto; no usaremos `day_of_week` como feature porque el nivel de señal es semanal.

## Pregunta 2 — ¿Qué productos generan el valor?

### Concentración

- **1049 productos** (21.50% del catálogo) generan el **80% del ingreso**.
- Total de productos con ingresos positivos: 4879

[Ver gráfico interactivo](figures/q2_concentration.html)

### Clasificación de tendencias

| trend           |   n_products |
|:----------------|-------------:|
| stable          |          913 |
| growing         |          685 |
| new_launch      |          501 |
| declining       |          359 |
| dead            |           91 |
| anomaly_returns |           78 |
| dormant         |            4 |

**Top 10 productos en crecimiento (base comparable):**

|   stock_code |   units_recent |   units_previous |   delta |   growth_pct |
|-------------:|---------------:|-----------------:|--------:|-------------:|
|        84347 |           6081 |            -6887 |   12968 |        188.3 |
|        22197 |          31535 |            18694 |   12841 |         68.7 |
|        22952 |          13634 |             1360 |   12274 |        902.5 |
|        22086 |          14236 |             2552 |   11684 |        457.8 |
|        22577 |           9407 |              385 |    9022 |       2343.4 |
|        22578 |           8971 |              126 |    8845 |       7019.8 |
|        84879 |          20907 |            13885 |    7022 |         50.6 |
|        20668 |           8973 |             2436 |    6537 |        268.3 |
|        21915 |          13569 |             7145 |    6424 |         89.9 |
|        22909 |           7107 |              905 |    6202 |        685.3 |

**Top 10 productos en declive (reales):**

|   stock_code |   units_recent |   units_previous |   delta |   growth_pct |
|-------------:|---------------:|-----------------:|--------:|-------------:|
|        22693 |           4892 |            11023 |   -6131 |        -55.6 |
|        22084 |            166 |             4757 |   -4591 |        -96.5 |
|        22053 |             43 |             4200 |   -4157 |        -99   |
|        22834 |            535 |             4104 |   -3569 |        -87   |
|        22740 |           1131 |             4615 |   -3484 |        -75.5 |
|        22440 |           1244 |             4716 |   -3472 |        -73.6 |
|        22087 |            557 |             3354 |   -2797 |        -83.4 |
|        22243 |            152 |             2935 |   -2783 |        -94.8 |
|        40016 |            517 |             3079 |   -2562 |        -83.2 |
|        18007 |            398 |             2652 |   -2254 |        -85   |

### 🚀 Productos nuevos (501)

Lanzados después de feb-2011. **No tienen `growth_pct`** (no hay base comparable). Se evalúan por métricas absolutas: `units_per_month`, `n_invoices`, `avg_units_per_invoice`.

|   stock_code | first_sale_date     |   units_recent |   units_per_month_recent |   n_invoices_recent |   avg_units_per_invoice |
|-------------:|:--------------------|---------------:|-------------------------:|--------------------:|------------------------:|
|        23084 | 2011-05-10 00:00:00 |          24242 |                   4040.3 |                 793 |                    30.6 |
|        23203 | 2011-05-06 00:00:00 |          16789 |                   2798.2 |                1044 |                    16.1 |
|        23310 | 2011-06-09 00:00:00 |          11565 |                   1927.5 |                 227 |                    50.9 |
|        23307 | 2011-06-03 00:00:00 |          11350 |                   1891.7 |                 605 |                    18.8 |
|        23199 | 2011-04-11 00:00:00 |          10689 |                   1781.5 |                 742 |                    14.4 |
|        23209 | 2011-05-08 00:00:00 |          10387 |                   1731.2 |                 911 |                    11.4 |
|        23201 | 2011-04-11 00:00:00 |           9647 |                   1607.8 |                 687 |                    14   |
|        23344 | 2011-06-15 00:00:00 |           8948 |                   1491.3 |                 649 |                    13.8 |
|        23206 | 2011-04-11 00:00:00 |           8515 |                   1419.2 |                 765 |                    11.1 |
|        23202 | 2011-05-06 00:00:00 |           8377 |                   1396.2 |                 735 |                    11.4 |

### 💤 Productos dormidos (4)

Existían antes pero no vendieron en el período anterior (estacionalidad, baja rotación, o pausa). **No tienen `growth_pct`.**

| stock_code   | first_sale_date     |   units_recent |   units_per_month_recent |   n_invoices_recent |
|:-------------|:--------------------|---------------:|-------------------------:|--------------------:|
| 22950        | 2010-09-15 00:00:00 |           4884 |                    814   |                 189 |
| 21373        | 2009-12-04 00:00:00 |            427 |                     71.2 |                  43 |
| 81952V       | 2009-12-02 00:00:00 |            365 |                     60.8 |                  24 |
| 81952B       | 2010-01-11 00:00:00 |            200 |                     33.3 |                   9 |

### ⚠️ Anomalías de devoluciones (78)

Productos con más devoluciones que ventas en el período reciente. Puede ser ajuste de inventario o error de recolección. **Se excluyen del ranking de declives.**

| stock_code   |   units_recent |   units_previous |   delta |
|:-------------|---------------:|-----------------:|--------:|
| 23005        |         -14705 |               67 |  -14772 |
| 23003        |          -9010 |              494 |   -9504 |
| 79323W       |          -4830 |               -8 |   -4822 |
| 79323LP      |          -2618 |                0 |   -2618 |
| 21399        |           -154 |             1981 |   -2135 |

### Top 10 productos por ingreso

| stock_code   | description                         |   net_revenue |   units_sold |
|:-------------|:------------------------------------|--------------:|-------------:|
| 22423        | REGENCY CAKESTAND 3 TIER            |      314045   |        26495 |
| 85123A       | WHITE HANGING HEART T-LIGHT HOLDER  |      248338   |        98208 |
| 85099B       | JUMBO BAG RED RETROSPOT             |      178401   |        96764 |
| 47566        | PARTY BUNTING                       |      147080   |        28248 |
| 84879        | ASSORTED COLOUR BIRD ORNAMENT       |      128550   |        80090 |
| 22086        | PAPER CHAIN KIT 50'S CHRISTMAS      |      116299   |        35113 |
| 79321        | CHILLI LIGHTS                       |       79905.1 |        15988 |
| 22197        | SMALL POPCORN HOLDER                |       78903.6 |        88993 |
| 22386        | JUMBO BAG PINK POLKADOT             |       75457.6 |        39437 |
| 84347        | ROTATING SILVER ANGELS T-LIGHT HLDR |       70969.9 |        31522 |

## Pregunta 3 — ¿Qué patrones presentan los clientes?

- **Clientes identificados totales:** 5,942
- **Clientes recurrentes (más de 1 factura):** 4,481 (75.41%)
- **Frecuencia media de compra:** 7.55 facturas/cliente

[Ver gráfico interactivo](figures/q3_rfm.html)

**Distribución por segmento RFM:**

| rfm_segment   |   n_customers |   pct_customers |   avg_recency_days |   avg_frequency |   avg_monetary |    total_revenue |   pct_revenue |
|:--------------|--------------:|----------------:|-------------------:|----------------:|---------------:|-----------------:|--------------:|
| champion      |          1504 |           25.31 |                 18 |            18.9 |        7736.89 |      1.16363e+07 |         71.43 |
| loyal         |          1210 |           20.36 |                 78 |             6.6 |        1984.68 |      2.40146e+06 |         14.74 |
| at_risk       |           850 |           14.3  |                370 |             6   |        1576.58 |      1.34009e+06 |          8.23 |
| lost          |          1528 |           25.72 |                465 |             1.3 |         329.52 | 503509           |          3.09 |
| new           |           447 |            7.52 |                 27 |             1.5 |         464.52 | 207641           |          1.27 |
| regular       |           403 |            6.78 |                108 |             1.5 |         498.78 | 201009           |          1.23 |

## Pregunta 4 — ¿Qué mercados son más importantes?

- **Reino Unido:** 84.78% del ingreso total.
- **Total de países:** 43

[Ver gráfico interactivo](figures/q4_markets.html)

**Top 10 países fuera del Reino Unido:**

| country     |   net_revenue |   units_sold |   n_customers |   pct_revenue |
|:------------|--------------:|-------------:|--------------:|--------------:|
| EIRE        |      609954   |       336604 |             5 |          3.23 |
| Netherlands |      548331   |       384519 |            23 |          2.91 |
| Germany     |      411959   |       225173 |           107 |          2.18 |
| France      |      321733   |       271902 |            95 |          1.71 |
| Australia   |      166444   |       104067 |            15 |          0.88 |
| Switzerland |       99403.1 |        52763 |            22 |          0.53 |
| Spain       |       91013.4 |        50318 |            41 |          0.48 |
| Sweden      |       87775.5 |        88633 |            19 |          0.47 |
| Denmark     |       64459.6 |       237471 |            12 |          0.34 |
| Belgium     |       63208.9 |        34778 |            29 |          0.34 |

## Pregunta 5 — ¿Qué productos se pueden prever con fiabilidad?

Total de productos: 5,285

| forecastability   |   n_products |
|:------------------|-------------:|
| intermittent      |         2392 |
| low_volume        |         1257 |
| forecastable      |         1085 |
| high_variance     |          551 |

[Ver gráfico interactivo](figures/q5_forecastability.html)

**Interpretación:**

- `forecastable`: productos con volumen razonable y estacionalidad estable. Candidatos a forecasting individual.
- `intermittent`: más del 50% de semanas sin venta. Requieren modelos agregados o métodos específicos para demanda intermitente (Croston).
- `high_variance`: CV > 1.5. Predicción individual muy ruidosa.
- `low_volume`: < 50 unidades totales. No merece la pena predecir individualmente.

**Ejemplos de productos forecastable (top 10 por volumen):**

| stock_code   |   n_active_weeks |   total_units |   mean_weekly_units |   cv |
|:-------------|-----------------:|--------------:|--------------------:|-----:|
| 84077        |              102 |        104883 |             1028.26 | 0.95 |
| 85123A       |              103 |         97393 |              945.56 | 0.69 |
| 85099B       |              103 |         95659 |              928.73 | 0.5  |
| 21212        |              103 |         94425 |              916.75 | 0.53 |
| 22197        |              103 |         82776 |              803.65 | 1.08 |
| 84879        |              103 |         78760 |              764.66 | 0.92 |
| 21977        |              103 |         55827 |              542.01 | 0.72 |
| 84991        |              103 |         53892 |              523.22 | 0.64 |
| 15036        |              101 |         44323 |              438.84 | 1.2  |
| 22492        |               82 |         43254 |              527.49 | 0.71 |

## Limitaciones de los datos

- **Dataset sin documentación**: Online Retail II es un dataset público sin información sobre su recolección. Las anomalías pueden ser reales o errores; no podemos determinarlo.
- **Anomalías de devoluciones**: algunos productos tienen más devoluciones que ventas en ciertos períodos (`anomaly_returns`). Se excluyen del ranking de declives para no distorsionar el análisis.
- **Pedidos mayoristas cancelados**: se usa `units_net_line` (ventas - cancelaciones - devoluciones) para netear pedidos cancelados.
- **Los productos con un porcentaje de growth muy alto, se debe a que en el periodo anterior no se vendieron unidades, debido a estacionalidad o a nuevas salidas al mercado,lo que resulta en un crecimiento relativo elevado.**
- **Pedidos mayoristas puntuales**: productos con líneas > 10.000 unidades se marcan como `wholesale_dependent`.
- **Mes parcial**: diciembre 2011 está incompleto (9 días). Se excluye de los análisis temporales.
- **Sábados**: solo hay 1 día con ventas en sábado en 2 años. El negocio opera principalmente de lunes a viernes.

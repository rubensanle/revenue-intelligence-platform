# Informe de calidad — Online Retail II

_Generado automáticamente por `src/quality/quality_report.py`._


## 1. Panorama general
- **Filas:** 525,461
- **Columnas:** 8
- **Rango temporal:** 2009-12-01 07:45:00 → 2010-12-09 20:01:00
- **Fecha del informe:** 2026-10-15 15:26

**Esquema:**

| column_name   | column_type   |
|:--------------|:--------------|
| Invoice       | VARCHAR       |
| StockCode     | VARCHAR       |
| Description   | VARCHAR       |
| Quantity      | BIGINT        |
| InvoiceDate   | TIMESTAMP_NS  |
| Price         | DOUBLE        |
| Customer ID   | DOUBLE        |
| Country       | VARCHAR       |


## 2. Valores nulos
Total de filas: **525,461**

| columna     |   nulos | porcentaje   |
|:------------|--------:|:-------------|
| Invoice     |       0 | 0.00%        |
| StockCode   |       0 | 0.00%        |
| Description |    2928 | 0.56%        |
| Quantity    |       0 | 0.00%        |
| InvoiceDate |       0 | 0.00%        |
| Price       |       0 | 0.00%        |
| Customer ID |  107927 | 20.54%       |
| Country     |       0 | 0.00%        |


## 3. Duplicados
- **Duplicados exactos (filas completas):** 6,418
- **Grupos duplicados por (Invoice, StockCode, Quantity, Price):** 6,419

_Nota: los duplicados por clave de negocio pueden ser legítimos (misma línea repetida en la misma factura) o errores de registro._


## 4. Quantity y Price
**Quantity (unidades):**

|   min |   max |   media |   mediana | negativas      | cero      |
|------:|------:|--------:|----------:|:---------------|:----------|
| -9600 | 19152 |   10.34 |         3 | 12,326 (2.35%) | 0 (0.00%) |

**Price (precio unitario en GBP):**

|      min |     max |   media |   mediana | negativos   | cero          |
|---------:|--------:|--------:|----------:|:------------|:--------------|
| -53594.4 | 25111.1 |  4.6888 |       2.1 | 3 (0.00%)   | 3,687 (0.70%) |

_Interpretación: Quantity negativa suele indicar devolución. Price = 0 puede indicar muestras gratuitas, ajustes o errores._


## 5. Cancelaciones (Invoice comienza por 'C')
- **Total de líneas con Invoice 'C%':** 10,206 (1.94% del dataset)
- De esas: 10,205 con Quantity < 0, 1 con Quantity > 0, 0 con Quantity = 0.

_Nota: una cancelación debería tener Quantity negativa. Si hay positivas, son ajustes o casos atípicos que requieren revisión._


## 6. Códigos que no son productos reales
Estos códigos representan cargos, ajustes, portes o pruebas. Deben excluirse de análisis de producto y forecasting.

| StockCode    |   n |     revenue |
|:-------------|----:|------------:|
| POST         | 865 |   46092.4   |
| M            | 850 |  -14122.1   |
| DOT          | 736 |  116402     |
| C2           | 138 |    6400     |
| D            | 100 |   -7788.32  |
| BANK CHARGES |  65 |  -28387     |
| S            |  41 |   -3016.41  |
| gift_0001_30 |  21 |     434.56  |
| gift_0001_20 |  19 |     304.01  |
| PADS         |  15 |     -36.586 |
| TEST001      |  15 |     202.5   |
| AMAZONFEE    |   9 |  -39243.1   |
| gift_0001_10 |   7 |      51.24  |
| gift_0001_40 |   4 |      65.39  |
| gift_0001_50 |   4 |      86.03  |
| SP1002       |   3 |      14.75  |
| B            |   3 | -136552     |
| TEST002      |   2 |       1     |


## 7. Clientes sin identificador
Las ventas sin Customer ID no pueden atribuirse a un cliente. Se analizarán por separado cuando corresponda (RFM, cohortes).

| tipo   |   lineas |     revenue | porcentaje_lineas   |
|:-------|---------:|------------:|:--------------------|
| Sin ID |   107927 | 1.19128e+06 | 20.54%              |
| Con ID |   417534 | 8.34821e+06 | 79.46%              |


## 8. Cobertura temporal
- **Meses cubiertos:** 13
- **Primer mes:** 2009-12-01 00:00:00
- **Último mes:** 2010-12-01 00:00:00

_Nota: diciembre 2011 puede estar incompleto (el dataset termina el 9-dic-2011)._


## 9. Outliers (método IQR)
- **Quantity:** rango normal [-12, 24]. Outliers: 57,870 (11.01%).
- **Price:** rango normal [-3.19, 8.65]. Outliers: 35,273 (6.71%).

_Nota: los outliers NO se eliminan automáticamente. Pueden ser ventas mayoristas legítimas o errores. Requieren inspección._

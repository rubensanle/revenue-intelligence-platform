# Informe de calidad — Online Retail II

_Generado automáticamente por `src/quality/quality_report.py`._


## 1. Panorama general
- **Filas:** 1,067,371
- **Columnas:** 8
- **Rango temporal:** 2009-12-01 07:45:00 → 2011-12-09 12:50:00
- **Fecha del informe:** 2026-10-18 15:32

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
Total de filas: **1,067,371**

| columna     |   nulos | porcentaje   |
|:------------|--------:|:-------------|
| Invoice     |       0 | 0.00%        |
| StockCode   |       0 | 0.00%        |
| Description |    4382 | 0.41%        |
| Quantity    |       0 | 0.00%        |
| InvoiceDate |       0 | 0.00%        |
| Price       |       0 | 0.00%        |
| Customer ID |  243007 | 22.77%       |
| Country     |       0 | 0.00%        |


## 3. Duplicados
- **Duplicados exactos (filas completas):** 32,907
- **Grupos duplicados por (Invoice, StockCode, Quantity, Price):** 32,911

_Nota: los duplicados por clave de negocio pueden ser legítimos (misma línea repetida en la misma factura) o errores de registro._


## 4. Quantity y Price
**Quantity (unidades):**

|    min |   max |   media |   mediana | negativas      | cero      |
|-------:|------:|--------:|----------:|:---------------|:----------|
| -80995 | 80995 |    9.94 |         3 | 22,950 (2.15%) | 0 (0.00%) |

**Price (precio unitario en GBP):**

|      min |   max |   media |   mediana | negativos   | cero          |
|---------:|------:|--------:|----------:|:------------|:--------------|
| -53594.4 | 38970 |  4.6494 |       2.1 | 5 (0.00%)   | 6,202 (0.58%) |

_Interpretación: Quantity negativa suele indicar devolución. Price = 0 puede indicar muestras gratuitas, ajustes o errores._


## 5. Cancelaciones (Invoice comienza por 'C')
- **Total de líneas con Invoice 'C%':** 19,494 (1.83% del dataset)
- De esas: 19,493 con Quantity < 0, 1 con Quantity > 0, 0 con Quantity = 0.

_Nota: una cancelación debería tener Quantity negativa. Si hay positivas, son ajustes o casos atípicos que requieren revisión._


## 6. Códigos que no son productos reales
Estos códigos representan cargos, ajustes, portes o pruebas. Deben excluirse de análisis de producto y forecasting.

| StockCode    |    n |     revenue |
|:-------------|-----:|------------:|
| POST         | 2122 |  112341     |
| DOT          | 1446 |  322647     |
| M            | 1421 |  -82796.3   |
| C2           |  282 |   13386     |
| D            |  177 |  -13484.5   |
| S            |  104 |   -6065.8   |
| BANK CHARGES |  102 |  -35562.6   |
| AMAZONFEE    |   43 | -260764     |
| gift_0001_30 |   29 |     610.09  |
| gift_0001_20 |   29 |     471.06  |
| PADS         |   19 |     -36.583 |
| gift_0001_10 |   16 |     126.21  |
| CRUK         |   16 |   -7933.43  |
| TEST001      |   15 |     202.5   |
| gift_0001_50 |    8 |     253.59  |
| gift_0001_40 |    7 |     166.09  |
| B            |    6 | -147614     |
| SP1002       |    3 |      14.75  |
| TEST002      |    2 |       1     |


## 7. Clientes sin identificador
Las ventas sin Customer ID no pueden atribuirse a un cliente. Se analizarán por separado cuando corresponda (RFM, cohortes).

| tipo   |   lineas |     revenue | porcentaje_lineas   |
|:-------|---------:|------------:|:--------------------|
| Sin ID |   243007 | 2.63896e+06 | 22.77%              |
| Con ID |   824364 | 1.66483e+07 | 77.23%              |


## 8. Cobertura temporal
- **Meses cubiertos:** 25
- **Primer mes:** 2009-12-01 00:00:00
- **Último mes:** 2011-12-01 00:00:00

_Nota: diciembre 2011 puede estar incompleto (el dataset termina el 9-dic-2011)._


## 9. Outliers (método IQR)
- **Quantity:** rango normal [-12, 24]. Outliers: 116,489 (10.91%).
- **Price:** rango normal [-3.10, 8.50]. Outliers: 68,105 (6.38%).

_Nota: los outliers NO se eliminan automáticamente. Pueden ser ventas mayoristas legítimas o errores. Requieren inspección._

# Catálogo de precios de reparación (`precios_reparacion_vehiculos.csv`)

**Todos los valores son estimaciones de referencia** (`es_estimacion = true`), no cotizaciones de talleres.
Sirven para dar un rango orientativo; el monto final depende de la inspección física del vehículo.

## Estructura
7.065 filas = 157 modelos × 45 combinaciones (5 piezas × 3 severidades × 3 tipos de establecimiento).
Moneda COP. Piezas: Bumper delantero, Bumper trasero, Capó, Guardabarros, Puerta.

## De dónde sale cada grupo de filas
| Grupo | Filas | Columna `origen` |
|---|---|---|
| BMW, Mazda y Toyota (21 modelos) | 945 | `estimacion_referencia_previamente_definida` — definidas por el equipo, **no se modificaron** |
| Marcas y modelos añadidos (136 modelos) | 6.120 | `estimacion_segmento_ancla_<Marca>_<Modelo>_x<factor>_2026-10` |

## Método de las filas añadidas
1. Se eligieron las marcas y modelos con más circulación en Colombia según el ranking de ventas 2025 y 2026
   (ANDI/Fenalco, publicado por El Carro Colombiano, El Colombiano y La República), más marcas premium y de
   importación presentes en el mercado.
2. Cada modelo se asignó a un segmento y se le dio un **índice de costo** respecto a Mazda3 = 1,00
   (ej.: Picanto/Kwid/Spark 0,72–0,78; compactos 0,85–1,00; SUV compactas 1,00–1,10; SUV medianas y pickups
   1,10–1,25; premium 1,30–1,90). El criterio cualitativo de "autos económicos de reparar" (Kia Picanto y Rio,
   Renault Kwid y Sandero, Chevrolet Spark GT y Sail) viene de Fasecolda.
3. Las 45 filas del modelo se calculan multiplicando las del modelo **ancla** más cercano ya existente en el CSV
   (Mazda2 Sport, Mazda3, CX-5, Land Cruiser Prado, BMW Serie 5 o X5) por `índice / índice_del_ancla`, y se
   redondean a múltiplos de COP 10.000. El factor queda en `origen`.

## Límites
- Los índices por segmento son **supuestos del proyecto**, no precios publicados por marca.
  Para afinarlos, reemplazar las filas de un modelo por cotizaciones reales y cambiar su `origen`.
- Referencia de inflación (Asopartes, julio 2026, variación anual): latonería y pintura +5,07 %, repuestos
  −0,57 %, servicios de taller +10,34 %. Los precios previos no se reajustaron porque no tienen fecha de base.
- El nombre del modelo debe coincidir (sin importar mayúsculas, tildes ni espacios) con el de la columna `modelo`.

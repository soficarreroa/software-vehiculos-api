# Software Vehiculos API

FastAPI + SUPABASE
---

## 🚀 Despliegue en Render

### 1. Preparar el proyecto

Antes de desplegar, limpia el proyecto eliminando archivos innecesarios:

```bash
python cleanup.py
```

### 2. Subir a GitHub

```bash
git add .
git commit -m "Clean project for production deployment"
git push origin main
```

### 3. Desplegar en Render

1. Ve a [render.com](https://render.com) y crea una cuenta
2. Conecta tu repositorio de GitHub
3. Crea un nuevo **Web Service**
4. Configura:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### 4. Variables de entorno

En Render, configura estas variables de entorno:
- `SUPABASE_URL`: Tu URL de Supabase
- `SUPABASE_KEY`: Tu clave anónima de Supabase

### 5. ¡Listo!

Tu API estará disponible en la URL que Render te proporcione.

---

## 💻 Desarrollo Local

### Requirements

- Python 3.13+
- Supabase account

### Instalación

1. **Instala Python**
   Descarga desde https://python.org/downloads

2. **Clona el repositorio**
   ```bash
   git clone https://github.com/soficarreroa/software-vehiculos-api.git
   cd software-vehiculos-api
   ```

3. **Crea entorno virtual**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # macOS/Linux
   ```

4. **Instala dependencias**
   ```bash
   pip install -r requirements.txt
   ```

5. **Configura variables de entorno**
   ```bash
   cp .env_example .env
   ```
   Edita `.env` con tus credenciales de Supabase.

6. **Ejecuta el servidor**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Prueba**
   Abre `http://localhost:8000/docs` para la documentación interactiva.

---

## 📋 Endpoints

- `GET /api/v1/vehiculos` - Lista todos los vehículos
- `GET /api/v1/vehiculos/{id}` - Obtiene un vehículo específico
- `POST /api/v1/vehiculos` - Crea un nuevo vehículo
- `PUT /api/v1/vehiculos/{id}` - Actualiza un vehículo
- `DELETE /api/v1/vehiculos/{id}` - Elimina un vehículo
- `GET /api/v1/vehiculos/{id}/piezas-disponibles` - Piezas disponibles para un vehículo
- `POST /api/v1/cotizaciones/completa` - Crea una cotización completa
- `POST /api/v1/cotizaciones/estimar` - Calcula un estimado de reparación sin guardarlo
- `POST /api/v1/analisis/danos` - Analiza una imagen de vehículo con YOLO (requiere autenticación)
- `GET /api/v1/cotizaciones` - Lista todas las cotizaciones
- `GET /api/v1/talleres` - Lista talleres aliados
- `GET /api/v1/talleres/cercanos?lat={latitud}&lng={longitud}` - Lista talleres aliados ordenados por distancia

### Analizar daños en una imagen

El endpoint recibe una imagen JPEG, PNG o WEBP como `multipart/form-data`.
Requiere el token de acceso del usuario autenticado y acepta archivos de hasta
10 MB y 40 megapíxeles. En `/docs`, usa el botón **Authorize** e ingresa el
token de acceso sin comillas ni el prefijo `Bearer`; Swagger agrega ese prefijo
al encabezado automáticamente. No guarda la imagen: devuelve los tipos de daño
detectados y los detalles disponibles para cada uno, incluyendo confianza,
ubicación, severidad estimada y etiqueta de costo.

```bash
curl -X POST "http://localhost:8000/api/v1/analisis/danos" \
  -H "Authorization: Bearer <TOKEN>" \
  -F "imagen=@foto.jpg"
```

**Respuesta exitosa (200)** — si no se encontró ningún daño, `danos_detectados` viene vacía y `mensaje` trae
`"No se detectaron daños en la foto"` (cuando sí hay daños, `mensaje` es `null`):

```json
{
  "imagen": "foto.jpg",
  "mensaje": null,
  "tipos_detectados": ["vidrio_roto"],
  "danos_detectados": [
    {
      "tipo_dano": "vidrio_roto",
      "clase_yolo": "glass shatter",
      "confianza": 0.943,
      "ubicacion": { "x1": 0.0, "y1": 14.2, "x2": 624.4, "y2": 406.1 },
      "ancho": 624.4,
      "alto": 391.9,
      "tiene_contorno": true,
      "area_relativa": 0.871,
      "severidad": "grave",
      "etiqueta_costo": "vidrio_roto_grave"
    }
  ]
}
```

`tipo_dano` puede ser `abolladura`, `rayon`, `grieta`, `vidrio_roto`, `luz_rota` o `llanta_baja`.
`severidad` es `leve`, `moderado` o `grave` (puede venir `null` si no hay umbrales calculados).
`etiqueta_costo` combina `tipo_dano` y `severidad` (ej. `vidrio_roto_grave`).
YOLO no identifica la pieza afectada: para estimar un costo hay que asignarla
explícitamente con el endpoint de estimación descrito más abajo.

**Errores posibles:**

| Código | Causa | Detalle que devuelve |
|---|---|---|
| 400 | Imagen vacía (0 bytes) | `La imagen está vacía` |
| 400 | El archivo no es una imagen válida o está corrupto | `El archivo no contiene una imagen válida` |
| 401 | Falta el token o es inválido/expirado | `Token no proporcionado` / `Token inválido o expirado` |
| 404 | El token es válido pero el usuario no existe en la tabla `usuarios` | `Usuario autenticado pero no encontrado en la base de datos` |
| 413 | La imagen pesa más de 10 MB, o tiene más de 40 megapíxeles | `La imagen supera el límite de 10 MB` / `...40 megapíxeles` |
| 415 | El `Content-Type` no es JPEG/PNG/WEBP, o no coincide con el contenido real del archivo | `Formato no permitido...` / `El tipo de contenido no coincide...` |
| 422 | La foto no es lo bastante clara: tiene menos de 200 px por lado, o está borrosa / sin detalle | `La foto tiene muy poca resolución...` / `La foto está borrosa o poco clara. Toma otra con buena luz, enfocada y más cerca del daño` |
| 503 | El modelo (`models/segmentador_cardd/best.pt`) no está disponible en el servidor | `El modelo de análisis de daños no está disponible` |
| 500 | Error inesperado al correr el modelo | `No se pudo completar el análisis de daños` |

**Qué tan bien detecta daños (resultado real de las pruebas, semana 10):** el modelo
se evaluó formalmente contra 399 fotos de prueba de CarDD (ver
[ENTRENAMIENTO_CARDD.md](ml/ENTRENAMIENTO_CARDD.md)): **F1 macro 0.616**. Por tipo de daño
el desempeño es muy desigual — `glass shatter` (vidrio roto) y `tire flat` (llanta baja) se
detectan bien (F1 0.96 y 0.89), pero `crack` (grieta) y `scratch` (rayón) todavía fallan mucho
(F1 0.19 y 0.45: se le escapan muchos rayones y grietas reales). Antes de confiar el estimado de
costo a esto, conviene que el equipo decida si ese nivel de precisión es aceptable para producción
o si hace falta más entrenamiento/dataset, sobre todo para rayón y grieta.

**Calidad de la foto:** antes de correr el modelo se revisa que la foto sea usable
(`app/services/calidad_imagen.py`): lado menor de al menos 200 px y nitidez medida con la varianza del
Laplaciano (umbral 10, calibrado con las fotos de `ml/resultados/set_fotos_extra/`; conviene recalibrarlo
con un set de fotos limpias). Una foto sin daños **no** es un error: responde 200 con el `mensaje` indicado arriba.

Este endpoint solo detecta y clasifica daños; no calcula costos por sí mismo.
La estimación se hace con `POST /api/v1/cotizaciones/estimar`.

### Estimar la reparación

`POST /api/v1/cotizaciones/estimar` calcula un rango de reparación en COP para
tres tipos de establecimiento: `economico`, `multimarca` y `concesionario`.
Requiere autenticación, valida que el vehículo pertenezca al usuario y **no
guarda la cotización ni escribe en Supabase**.

El catálogo usado es `data/precios_reparacion_vehiculos.csv` (945 filas, precios
de referencia para 3 marcas, 21 modelos y 5 categorías de pieza). No se consulta
la tabla `catalogo_precios` para este cálculo.

**Asignación de piezas:** la lista `asignaciones` relaciona cada índice de daño
con una pieza. Se aceptan las cinco categorías del CSV y estos nombres reales de
la tabla `piezas`:

| Nombre real | Categoría del CSV |
|---|---|
| `Parachoques Delantero` | `Bumper delantero` |
| `Parachoques Trasero` | `Bumper trasero` |
| `Guardabarros Delantero Derecho` | `Guardabarros` |
| `Puerta Delantera Izquierda` | `Puerta` |
| `Capó` | `Capó` |

Las demás piezas reales (`Faro Principal Derecho`, `Puerta Maletero`,
`Airbag de Volante`, etc.) no tienen equivalencia y quedan pendientes. La
respuesta conserva el nombre original en `pieza_original` y usa `pieza` para la
categoría del CSV. Cuando son distintas, `es_categoria_generica` es `true` y se
incluye una advertencia: el valor es una referencia de categoría, no una
cotización exacta de esa pieza específica.

```bash
curl -X POST "http://localhost:8000/api/v1/cotizaciones/estimar" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "vehiculo_id": 1,
    "danos": [
      {"tipo_dano": "rayon", "severidad": "moderado", "confianza": 0.91}
    ],
    "asignaciones": [
      {"indice_dano": 0, "pieza": "Parachoques Delantero"}
    ]
  }'
```

La respuesta incluye `desglose` por categoría de pieza, `precios` por
establecimiento, `totales`, `danos_no_estimados`, `danos_ignorados`,
`piezas_sin_precio`, `advertencias` y `nota`. También informa `marca_csv`,
`modelo_csv`, `anio_detectado` y `coincidencia_modelo` (`exacta` o
`modelo_base`). Los totales se redondean al múltiplo de COP 10.000 más cercano y
solo se consideran completos cuando todos los daños y todas las piezas tienen
precio.

**Vehículos y años:** marca y modelo se comparan normalizando mayúsculas,
espacios y acentos. Si el modelo del vehículo termina en un año explícito
(`2023`, `2020`, etc.) y el CSV tiene el modelo base sin año, se usa ese modelo
como referencia aproximada y se informa en `advertencias` que el precio no es
específico del año. Si la correspondencia no es inequívoca, el daño queda
pendiente; no se corrigen errores ortográficos ni se inventan modelos o precios.

Limitaciones actuales:

- El CSV cubre menos vehículos que la base de datos; los vehículos no
  reconocidos quedan pendientes.
- La categoría de pieza puede ser más general que el nombre real de la pieza.
- Varios daños de la misma categoría se agrupan y se cobran una sola vez con la
  severidad más alta.
- No se incluyen mano de obra, pintura ni repuestos adicionales distintos de los
  rangos del CSV.

**Pruebas específicas:**

```bash
python -m pytest tests/test_estimacion_reparacion.py -q
```

### Talleres cercanos a la ubicación del usuario

El cliente debe obtener la ubicación del dispositivo y enviar sus coordenadas
como parámetros `lat` y `lng` al endpoint de talleres cercanos:

```javascript
navigator.geolocation.getCurrentPosition(async ({ coords }) => {
   const params = new URLSearchParams({
      lat: String(coords.latitude),
      lng: String(coords.longitude),
   });

   const response = await fetch(
      `${API_URL}/api/v1/talleres/cercanos?${params}`
   );

   if (!response.ok) {
      throw new Error('No se pudieron obtener los talleres cercanos');
   }

   const talleres = await response.json();
   // Cada taller incluye distancia_km y viene ordenado del más cercano al más lejano.
}, (error) => {
   console.error('No fue posible obtener la ubicación', error);
}, {
   enableHighAccuracy: true,
});
```

La ubicación requiere permiso del usuario y debe solicitarse desde un contexto
seguro (`https` o `localhost`). La API valida que `lat` esté entre `-90` y `90`
y que `lng` esté entre `-180` y `180`.

## Entrenamiento del modelo de daños

El dataset, los comandos para reproducir el entrenamiento y su atribución están
documentados en [ENTRENAMIENTO_CARDD.md](ml/ENTRENAMIENTO_CARDD.md).

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
`etiqueta_costo` combina `tipo_dano` y `severidad` (ej. `vidrio_roto_grave`) y es la clave pensada
para cruzar contra la tabla de costos — **todavía no hay un endpoint que haga ese cruce
automáticamente** (ver "Pendiente" más abajo).

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

**Pendiente:** este endpoint solo detecta y clasifica daños — no calcula ningún costo. Cruzar
`etiqueta_costo` con el catálogo real de precios (tablas `piezas` y `catalogo_precios`) y sumar
un estimado total todavía no está implementado.

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

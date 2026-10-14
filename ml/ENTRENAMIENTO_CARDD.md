# Fine-tuning de YOLOv8n-seg con CarDD (propuesta)

Alternativa al modelo de `models/segmentador_danos` (Car Damage Images v3, 300 imágenes, clases por zona).
Este modelo usa **CarDD** (4,000 imágenes) y devuelve los 6 tipos de daño de la tabla de costos:
`crack`, `dent`, `glass shatter`, `lamp broken`, `scratch`, `tire flat`. No incluye severidad.

## Resultados (conjunto de prueba, 399 imágenes, 877 daños)

Entrenamiento: YOLOv8n-seg, 20 épocas, `imgsz=320`, `batch=8`, CPU (3.86 h). Umbral de confianza 0.25.
Precisión macro 0.644, recall macro 0.619, **F1 macro 0.616** (425 aciertos, 304 falsas, 452 no detectados).

| Clase | Aciertos | Falsas | No det. | Precisión | Recall | F1 |
|---|---|---|---|---|---|---|
| crack | 13 | 20 | 92 | 0.394 | 0.124 | 0.188 |
| dent | 115 | 89 | 132 | 0.564 | 0.466 | 0.510 |
| glass shatter | 65 | 3 | 2 | 0.956 | 0.970 | 0.963 |
| lamp broken | 54 | 36 | 13 | 0.600 | 0.806 | 0.688 |
| scratch | 149 | 151 | 211 | 0.497 | 0.414 | 0.452 |
| tire flat | 29 | 5 | 2 | 0.853 | 0.935 | 0.892 |

No se puede comparar directamente con el F1 del modelo anterior (0.279): cambian las clases y el conjunto de prueba (30 imágenes).

## Requisitos

No hay dependencias nuevas: `requirements.txt` ya incluye `ultralytics==8.4.174`.

```
pip install -r requirements.txt
```

## Reproducir el entrenamiento

1. Descargar **Carsdd v3** en formato **YOLOv8** desde https://universe.roboflow.com/dr-ulglr/carsdd
   y descomprimirlo en `carsdd/` (carpeta ignorada por Git; debe existir `carsdd/data.yaml`).
2. Dividir en train / valid / test (la versión descargada viene toda en train). Misma semilla = misma división:

   ```
   python dividir_dataset.py --dataset carsdd
   ```

3. Verificar el dataset. La huella del conjunto de prueba debe ser **`111f8a82857ce08d`**
   (lista de referencia en `models/segmentador_cardd/test_manifest.txt` y `split_manifest.csv`):

   ```
   python verificar_dataset.py --data carsdd/data.yaml
   ```

4. Entrenar (parte de `yolov8n-seg.pt`; guarda en `models/segmentador_cardd/`):

   ```
   python entrenar_cardd.py --data carsdd/data.yaml --epochs 20 --imgsz 320 --batch 8 --device cpu --workers 0 --name cardd_20
   ```

5. Evaluar con el mismo método de `evaluar_detector.py` (usar el mismo `--imgsz` del entrenamiento):

   ```
   python evaluar_cardd.py --data carsdd/data.yaml --imgsz 320
   ```

6. Probar con fotos (devuelve las clases de daño encontradas y guarda imágenes anotadas):

   ```
   python probar_cardd.py --fotos carsdd/test/images --cantidad 8 --imgsz 320
   ```

## Archivos

- `models/segmentador_cardd/best.pt`: pesos del modelo entrenado (20 épocas, `imgsz=320`).
- `models/segmentador_cardd/split_manifest.csv`: imagen y split (train/valid/test) de las 4,000 imágenes.
- `models/segmentador_cardd/test_manifest.txt`: imágenes de prueba con su huella.

## Severidad (estimada con el propio dataset)

CarDD no trae severidad. `severidad.py` la **define** con los datos de CarDD, sin etiquetas de personas ni de otras IA:
para cada daño toma la fracción de la foto que ocupa su máscara (`area_relativa`) y la compara con los daños del mismo tipo
en las 4,000 imágenes del dataset. Los tercios más pequeños son `leve`, los intermedios `moderado` y los más grandes `grave`
(umbrales por clase en `app/services/severidad_umbrales.json`).

Qué significa y qué no:

- Es una definición por **tamaño relativo**, no una medición de la gravedad real de la reparación: no ve profundidad,
  pieza rota ni metal expuesto, y depende de qué tan cerca se tomó la foto.
- No está contrastada con el criterio de un perito. Una comparación inicial con etiquetas hechas por una IA dio poco acuerdo
  (kappa 0.17), pero esas etiquetas tampoco son una verdad de referencia: solo indican que no coinciden. Verificarla
  requeriría etiquetas de un perito sobre una muestra de fotos.
- Cada daño trae `area_relativa`, `severidad` y `etiqueta_costo` (por ejemplo `rayon_moderado`, con la nomenclatura de las
  18 clases de la tabla de costos).

1. Calcular los umbrales (una vez, con el dataset descargado) y dejar `severidad_umbrales.json` junto a `severidad.py`:

   ```
   python ml/data/calcular_umbrales_severidad.py --labels carsdd/train/labels --data carsdd/data.yaml --salida app/services/severidad_umbrales.json
   ```

2. `traducir_salida_yolo.py` agrega esos tres campos a cada daño. Si no existe el JSON de umbrales, `severidad` queda en `null`.

## Salida simplificada (traducir_salida_yolo.py)

Devuelve, para una foto, la lista de tipos de daño encontrados y el detalle de cada uno. Las clases del modelo
(inglés) se traducen a los tipos de la tabla de costos: `crack` -> `grieta`, `dent` -> `abolladura`,
`glass shatter` -> `vidrio_roto`, `lamp broken` -> `luz_rota`, `scratch` -> `rayon`, `tire flat` -> `llanta_baja`.

```
python traducir_salida_yolo.py ruta/a/la/foto.jpg 0.25
```

## Mejora posible

El mAP50 de validación seguía subiendo en la época 20, y `crack` y `scratch` son las clases más débiles.
Con una GPU se puede entrenar más tiempo y a mayor resolución en una sola corrida (no continuar desde `last.pt`,
porque eso reinicia el optimizador):

```
python entrenar_cardd.py --data carsdd/data.yaml --epochs 50 --imgsz 640 --batch 16 --device 0 --name cardd_50_640
python evaluar_cardd.py --data carsdd/data.yaml --imgsz 640
```

Para que el resultado sea comparable hay que usar el mismo conjunto de prueba (misma huella).

## Licencia y atribución

CarDD, licencia CC BY 4.0. Conservar la atribución al autor del dataset en Roboflow (dr-ulglr)
y el enlace a la fuente: https://universe.roboflow.com/dr-ulglr/carsdd (proyecto original: https://cardd-ustc.github.io).

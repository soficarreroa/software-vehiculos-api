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

## Umbral de confianza usado por la API

La configuración activa de la API es el candidato `models/segmentador_cardd_candidato_416_25/best.pt`, con `imgsz=416`
y `conf=0.30`. El umbral se seleccionó al evaluar validación de CarDD (801 imágenes, 1.742 daños anotados):
se compararon valores de 0.10 a 0.65 en incrementos de 0.05, y 0.30 obtuvo el mejor F1 macro (0.638).

Con ese umbral fijado en validación, el test final (399 imágenes) obtuvo F1 macro 0.629, precisión macro 0.637 y
recall macro 0.629. El checkpoint original se conserva en `models/segmentador_cardd/best.pt`; obtuvo F1 macro 0.611
en validación y 0.616 en test con `imgsz=320`, `conf=0.25`. Ambos resultados usan los mismos splits y el mismo
evaluador. El test no se usó para elegir el umbral. Los reportes están en `resultados_cardd/` y
`resultados_cardd_candidato_416_25/`. La constante `CONFIANZA_MINIMA` y `IMGSZ` en
`app/services/traducir_salida_yolo.py` determinan la configuración por defecto de la API.

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

4. Entrenar (parte de `yolov8n-seg.pt`; usa una carpeta separada para no sobrescribir el checkpoint activo):

   ```
   python ml/training/entrenar_cardd.py --data carsdd/data.yaml --epochs 20 --imgsz 320 --batch 8 --device cpu --workers 0 --name cardd_reproduccion_320 --model-dir models/segmentador_cardd_reproduccion_320
   ```

5. Evaluar con el mismo método de `evaluar_detector.py` (usar el mismo `--imgsz` del entrenamiento):

   ```
   python evaluar_cardd.py --data carsdd/data.yaml --imgsz 320
   ```

6. Probar con fotos (devuelve las clases de daño encontradas y guarda imágenes anotadas):

   ```
   python probar_cardd.py --fotos carsdd/test/images --cantidad 8 --imgsz 320
   ```

## Entrenar un candidato sin reemplazar el modelo activo

El checkpoint original se conserva en `models/segmentador_cardd/`. Los experimentos nuevos deben guardar sus pesos
en una carpeta aparte y sus reportes en otra. El script rechaza explícitamente `models/segmentador_cardd/` como destino.

En la máquina revisada no hay CUDA disponible (entrenamiento solo en CPU). Para investigar si más resolución y más
épocas ayudan con grietas y rayones, la configuración propuesta es 640 px, 50 épocas como máximo, batch 4 y early
stopping con paciencia 15. Es una corrida potencialmente larga en CPU; conviene conectarla a corriente y no iniciar
hasta reservar suficiente tiempo. Esta configuración es un experimento, no una garantía de mejora.

Entrenar el candidato:

```powershell
python ml\training\entrenar_cardd.py --data carsdd\data.yaml --epochs 50 --imgsz 640 --batch 4 --device cpu --workers 0 --name cardd_candidato_640_50 --model-dir models\segmentador_cardd_candidato_640_50
```

Evaluarlo con el mismo split y seleccionar el umbral en validación:

```powershell
python -m ml.evaluation.evaluar_cardd --data .\carsdd\data.yaml --model .\models\segmentador_cardd_candidato_640_50\best.pt --reporte .\resultados_cardd_candidato_640_50 --imgsz 640
```

La evaluación escribe los resultados en `resultados_cardd_candidato_640_50/`. Compara sus métricas de validación
y test con la línea base en `resultados_cardd/`. El test solo se usa para la comparación final, no para elegir
hiperparámetros ni umbrales. Mantén el modelo activo hasta que el candidato supere la línea base en las métricas
que importan y haya sido revisado con fotos reales.

## Archivos

- `models/segmentador_cardd/best.pt`: pesos del modelo original (20 épocas, `imgsz=320`), conservado para reversión.
- `models/segmentador_cardd_candidato_416_25/best.pt`: candidato seleccionado (25 épocas, `imgsz=416`), usado actualmente por la API.
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

## Licencia y atribución

CarDD, licencia CC BY 4.0. Conservar la atribución al autor del dataset en Roboflow (dr-ulglr)
y el enlace a la fuente: https://universe.roboflow.com/dr-ulglr/carsdd (proyecto original: https://cardd-ustc.github.io).

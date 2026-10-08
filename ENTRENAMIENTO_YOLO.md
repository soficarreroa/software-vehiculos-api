# Modelo de segmentación de daños vehiculares

## Resumen

Este proyecto entrena YOLOv8n-seg para localizar daños en fotografías de
vehículos. Para cada región puede producir clase, confianza, caja y contorno
de segmentación. No predice nivel de severidad.

Las seis clases configuradas por el dataset son `Broken glass`, `Dent`,
`Scratch`, `front-end-damage`, `rear-end-damage` y `side-impact-damage`. Se usa
el formato YOLO-seg porque las etiquetas son polígonos; no se convierten las
imágenes a una sola etiqueta por foto.

## Dataset y atribución

El export usado es Car Damage Images, versión 3, provisto en
`Car Damage Images.v3i.yolov8/`. Se conservan sus splits oficiales:

| Split | Imágenes | Polígonos anotados |
| --- | ---: | ---: |
| train | 210 | 220 |
| valid | 60 | 64 |
| test | 30 | 31 |
| Total | 300 | 315 |

El dataset contiene algunas fotos con más de una clase y anotaciones vacías;
son válidas para detección/segmentación y se conservan. Los nombres y el orden
de clases oficiales están en `data.yaml`.

Fuente: [Car Damage Images, versión 3](https://universe.roboflow.com/car-damage-kadad/car-damage-images).
Publicador: `car-damage-kadad` en Roboflow Universe. Licencia declarada:
[Creative Commons Attribution 4.0 (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
Se conservaron `README.dataset.txt` y `README.roboflow.txt`. Si se redistribuye
el dataset, mantener esta atribución, enlazar la licencia e indicar que se
entrenó un modelo con el material.

## Archivos importantes

- `entrenar_detector.py`: entrenamiento inicial o continuación desde los pesos
	compartidos.
- `evaluar_detector.py`: elige un umbral en `valid` y mide una vez en `test`.
- `models/segmentador_danos/best.pt`: mejor checkpoint disponible; se usa para
	inferencia y evaluación.
- `models/segmentador_danos/last.pt`: pesos de la última época guardada; sirve
	como punto de partida para seguir ajustando.
- `resultados_deteccion/`: reportes generados localmente; se excluye de Git.
- `runs/`: logs, cachés y checkpoints de cada ejecución; se excluye de Git.

Los checkpoints compartidos pesan aproximadamente 26.5 MB cada uno. El modelo
de inicio `yolov8n-seg.pt` se descarga automáticamente cuando se inicia desde
cero y está excluido del repositorio para evitar duplicarlo.

## Preparar el entorno

En Windows, abre PowerShell en la raíz del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

La dependencia Ultralytics está fijada a `8.4.174`, la versión utilizada en
este ensayo. No se debe subir `.venv/` ni archivos `.env`.

## Continuar el entrenamiento

El ensayo compartido se interrumpió manualmente después de guardar la época 40
de un máximo de 50. `best.pt` conserva los mejores pesos guardados y `last.pt`
los pesos de la última época completada.

Ejecuta:

```powershell
.\.venv\Scripts\python.exe entrenar_detector.py
```

Si encuentra `models/segmentador_danos/last.pt`, el script parte de esos pesos
y entrena hasta 10 épocas adicionales. Esto continúa el ajuste de los pesos,
pero inicia un optimizador nuevo; no es una reanudación exacta del estado
interno del optimizador interrumpido. Al terminar, actualiza `best.pt` y
`last.pt`. Si no encuentra `last.pt`, empieza desde `yolov8n-seg.pt` con un
máximo de 50 épocas. Para cambiar la continuación, ajustar
`CONTINUATION_EPOCHS` en el script.

La paciencia está configurada en 10 épocas sin mejora de validación. El
entrenamiento original corrió en CPU y tardó alrededor de 40 minutos para 40
épocas; el tiempo de cada compañero dependerá de su equipo.

## Evaluar y probar imágenes

Para comparar umbrales y evaluar el test reservado:

```powershell
.\.venv\Scripts\python.exe evaluar_detector.py
```

El script escoge el umbral con mejor F1 macro en `valid`, entre `0.25`, `0.35`,
`0.50` y `0.65`, usando emparejamiento de cajas a IoU 0.50. Luego calcula una
única evaluación en `test`. Los reportes se escriben en `resultados_deteccion/`.

Para inferir una imagen propia y guardar una visualización de las máscaras:

```powershell
.\.venv\Scripts\python.exe -c "from ultralytics import YOLO; YOLO('models/segmentador_danos/best.pt').predict(source='foto.jpg', conf=0.35, save=True)"
```

Reemplaza `foto.jpg` por la ruta de la imagen. Ultralytics guarda la salida
visual en `runs/segment/predict/`.

## Resultados del ensayo actual

La validación seleccionó el umbral `0.35`:

| Umbral | Precisión macro | Recall macro | F1 macro |
| ---: | ---: | ---: | ---: |
| 0.25 | 0.252 | 0.232 | 0.238 |
| 0.35 | 0.310 | 0.226 | 0.256 |
| 0.50 | 0.354 | 0.178 | 0.230 |
| 0.65 | 0.322 | 0.124 | 0.179 |

Con ese umbral, el resultado en `test` fue:

| Precisión macro | Recall macro | F1 macro | TP | FP | FN |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.301 | 0.261 | 0.279 | 11 | 7 | 20 |

El desglose de cajas por clase:

| Clase | TP | FP | FN | Precisión | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Broken glass | 2 | 1 | 1 | 0.667 | 0.667 | 0.667 |
| Dent | 0 | 0 | 1 | 0.000 | 0.000 | 0.000 |
| Scratch | 0 | 0 | 4 | 0.000 | 0.000 | 0.000 |
| front-end-damage | 7 | 4 | 7 | 0.636 | 0.500 | 0.560 |
| rear-end-damage | 2 | 2 | 3 | 0.500 | 0.400 | 0.444 |
| side-impact-damage | 0 | 0 | 4 | 0.000 | 0.000 | 0.000 |

Es un resultado preliminar y débil, con solo 30 imágenes de test. Las máscaras
se entrenaron, pero las métricas de este reporte comparan cajas derivadas de
los polígonos con IoU 0.50; no son métricas IoU de máscara. Ultralytics también
registró mAP de segmentación en `runs/segmentador_danos_6_clases/results.csv`.
Se necesita más variedad y ejemplos, especialmente para clases con pocos
aciertos, antes de usarlo en un flujo real.

## Crear una rama y subir los archivos

No se creó una rama ni se realizó un push. Ejecuta los comandos en un clon Git
con permiso de escritura al repositorio o a tu fork. Primero verifica:

```powershell
git rev-parse --show-toplevel
git remote -v
```

Si el primer comando reconoce el repositorio, desde su raíz crea la rama,
prepara los archivos y revisa el contenido antes del commit:

```powershell
git switch -c feature/yolo-segmentacion-danos
git add .gitignore README.md requirements.txt ENTRENAMIENTO_YOLO.md entrenar_detector.py evaluar_detector.py "Car Damage Images.v3i.yolov8" models/segmentador_danos
git diff --cached --check
git diff --cached --stat
git status --short
git commit -m "Add vehicle damage segmentation model"
git push -u origin feature/yolo-segmentacion-danos
```

Comprueba en `git status` que aparezcan el dataset y ambos `.pt`. No agregues
`.venv/`, `.env`, `runs/` ni `resultados_deteccion/`; ya están excluidos por
`.gitignore`. Cada checkpoint pesa menos de 100 MB, el límite habitual de GitHub
para un archivo individual; si alguna imagen excediera ese límite, usar Git LFS
para ese archivo.

Si `git rev-parse` falla, esta carpeta no es un clon. Clona tu repositorio o
fork y copia allí los archivos preparados antes de crear la rama. En PowerShell,
reemplaza la URL de ejemplo por la URL HTTPS de tu fork (recomendado si no tienes
permisos de escritura en el repositorio original):

```powershell
$repoUrl = "https://github.com/<USUARIO>/<REPOSITORIO>.git"
$source = "C:\Users\DiDi\Downloads\software-vehiculos-api-main\software-vehiculos-api-main"
$repo = "C:\Users\DiDi\Downloads\software-vehiculos-api"
git clone $repoUrl $repo
Copy-Item "$source\.gitignore", "$source\README.md", "$source\requirements.txt", "$source\ENTRENAMIENTO_YOLO.md", "$source\entrenar_detector.py", "$source\evaluar_detector.py" -Destination $repo -Force
Copy-Item "$source\Car Damage Images.v3i.yolov8" -Destination $repo -Recurse -Force
Copy-Item "$source\models" -Destination $repo -Recurse -Force
Set-Location $repo
```

Después ejecuta allí los comandos de rama, `git add`, commit y `git push` de la
sección anterior. No pegues la URL de ejemplo literalmente: reemplaza ambos
marcadores por tu usuario y el nombre del repositorio/fork.
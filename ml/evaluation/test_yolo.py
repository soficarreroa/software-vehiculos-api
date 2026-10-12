from ultralytics import YOLO

# Carga el modelo preentrenado más liviano (se descarga automáticamente la primera vez)
model = YOLO("yolov8n.pt")

# Imágenes de ejemplo que trae Ultralytics (se descargan solas la primera vez)
imagenes_ejemplo = [
    "runs/detect/predict/imagenes_prueba/accidente bomper.png",
    "runs/detect/predict/imagenes_prueba/espejo roto.png",
]
# Corre la detección y guarda los resultados con las cajas dibujadas
resultados = model.predict(source=imagenes_ejemplo, save=True)

for r in resultados:
    print(f"\nImagen: {r.path}")
    print(f"Objetos detectados: {len(r.boxes)}")
    for box in r.boxes:
        clase = model.names[int(box.cls[0])]
        confianza = float(box.conf[0])
        print(f"  - {clase} (confianza: {confianza:.2f})")

print("\nListo. Revisa la carpeta 'runs/detect/predict' para ver las imágenes con las detecciones dibujadas.")
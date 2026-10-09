Checkpoints compartidos para el segmentador de daños:

- `best.pt`: mejores pesos guardados durante el entrenamiento interrumpido en la época 40; usar para inferencia y evaluación.
- `last.pt`: últimos pesos guardados al interrumpir en la época 40; `entrenar_detector.py` los usa como inicialización para continuar el ajuste.

Ambos checkpoints corresponden a `Car Damage Images v3` y sus seis clases. El archivo `last.pt` continúa el ajuste desde los pesos, pero no restaura el estado del optimizador.

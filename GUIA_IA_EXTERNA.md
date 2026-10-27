# Análisis de daños con IA en un servicio aparte — guía para el equipo

Actualizado: 27 de octubre de 2026

## 1. Qué pasaba y qué se hizo

**Problema:** el backend principal (FastAPI, Render gratis con 512 MB de RAM) cargaba el modelo YOLO
(ultralytics + PyTorch) dentro del mismo servidor. Al procesar fotos se quedaba sin memoria y se caía.

**Solución:** el modelo ahora corre en **su propio servicio gratuito en Render**. El backend principal ya no
carga ultralytics ni PyTorch: le manda la foto por HTTP al servicio de IA y recibe las detecciones.

```
Frontend (Vercel)  ->  Backend principal (Render)  ->  Servicio de IA (Render)
                       POST /api/v1/analisis/danos     POST /detectar  (modelo YOLO)
```

**Servicio de IA**

- Repo: https://github.com/SalgadoCifu/software-vehiculos-ia
- URL: https://software-vehiculos-ia.onrender.com
- Rutas: `GET /health` (ver si está despierto), `POST /detectar` (analiza una foto), `/docs` (documentación)
- `POST /detectar` recibe la foto en el campo `imagen` y la clave en el header `x-api-key`.
- Responde, por ejemplo: `{"detecciones": [{"clase": "dent", "confianza": 0.70, "bbox": [x1, y1, x2, y2], "area_pct": 16.41}]}`
  (`area_pct` es el área del daño como % de la foto).

**Cambios en el backend principal**

| Archivo | Cambio |
|---|---|
| `app/services/cliente_ia.py` | Nuevo. Manda la foto al servicio de IA y maneja los errores (clave mala, URL mala, servicio dormido). |
| `app/services/traducir_salida_yolo.py` | Ya no carga YOLO. Traduce la lista `detecciones` del servicio de IA al mismo formato de siempre. |
| `app/routers/analisis_danos.py` | La llamada a la IA no bloquea el resto de la API mientras espera. Si la IA falla responde 503 (dormida) o 502 (error). |
| `requirements.txt` | Se quitó `ultralytics`. Se agregaron `requests`, `Pillow` y `numpy`. |
| `.env_example` | Se agregaron `IA_SERVER_URL` e `IA_API_KEY`. |

**Lo que NO cambió:** la ruta `POST /api/v1/analisis/danos`, el formato de su respuesta, las cotizaciones,
la severidad y la validación de calidad de imagen. Quien consume el endpoint no necesita cambiar nada
(salvo lo de la sección 4).

## 2. Qué debe hacer cada persona (una sola vez)

1. Actualizar el código:
   ```powershell
   git pull origin main
   ```
2. Agregar dos líneas a su archivo `.env` (el `.env` nunca se sube a git):
   ```
   IA_SERVER_URL=https://software-vehiculos-ia.onrender.com
   IA_API_KEY=<pedir la clave al equipo por privado>
   ```
3. Reinstalar dependencias (con el venv activado):
   ```powershell
   pip install -r requirements.txt
   ```
4. Levantar el backend. Ojo: el comando correcto es `app.main:app` (el README viejo dice `main:app`):
   ```powershell
   uvicorn app.main:app --reload --port 8000
   ```

**Solo si trabajan con los scripts de `ml/`** (entrenar o evaluar el modelo en local): esos scripts sí usan
ultralytics, que ya no viene en `requirements.txt`. Instálenlo aparte:
```powershell
pip install ultralytics==8.4.174
```

## 3. Cómo probar el análisis de fotos

Los servicios gratuitos de Render **se duermen tras unos 15 minutos sin uso**. Al despertar tardan
1–2 minutos, así que la primera foto es lenta. Las siguientes tardan unos segundos.

1. **Despertar la IA** antes de probar. Abrir en el navegador y esperar la respuesta:
   https://software-vehiculos-ia.onrender.com/health
2. Subir la foto como siempre: desde el frontend, o desde `/docs` del backend (local:
   http://localhost:8000/docs, endpoint `POST /api/v1/analisis/danos`).
3. Si sale "El servicio de análisis de daños está iniciando…", esperar 1–2 minutos y reintentar.

Pruebas en grupo: despierten la IA una vez y prueben todos seguidos; así nadie espera el arranque.

## 4. Para quien trabaja en el frontend

- La primera foto después de un rato sin uso puede tardar 1–2 minutos: mostrar un estado de "analizando…"
  y no cortar la petición antes de tiempo.
- El backend puede responder `503` (la IA está despertando) o `502` (error del servicio de IA). Ambos traen un
  mensaje en `detail` que se puede mostrar al usuario y conviene ofrecer un botón de "reintentar".
- Los errores que ya existían (400, 413, 415, 422) siguen igual.

## 5. Errores frecuentes

Los detalles técnicos quedan en los logs de Render (servicio → Logs). El usuario solo ve un mensaje amable.

| Qué se ve | Causa probable | Qué hacer |
|---|---|---|
| 503 "iniciando o no responde" | La IA estaba dormida | Abrir `/health`, esperar y reintentar. |
| 502 y en el log `rechazo la clave (401)` | `IA_API_KEY` distinta de `API_KEY` del servicio de IA | Copiar de nuevo la clave, sin espacios ni comillas. |
| 502 y en el log `respondio 404` | `IA_SERVER_URL` mal escrita | Debe ser solo `https://software-vehiculos-ia.onrender.com`, sin `/detectar`. |
| 503 que se repite aunque `/health` responde | Posible falta de memoria en el servicio de IA | Revisar logs del servicio de IA y probar con una foto más pequeña. |
| `Falta la variable de entorno IA_SERVER_URL` | No está en el `.env` o en Render | Agregarla (sección 2 o sección 6). |
| `ModuleNotFoundError` al arrancar | No se reinstalaron dependencias | `pip install -r requirements.txt` |

## 6. Variables de entorno

| Variable | Dónde | Valor |
|---|---|---|
| `IA_SERVER_URL` | `.env` local y Render (backend principal) | `https://software-vehiculos-ia.onrender.com` |
| `IA_API_KEY` | `.env` local y Render (backend principal) | La misma que `API_KEY` del servicio de IA |
| `IA_TIMEOUT` | Opcional | Segundos máximos de espera a la IA (por defecto 120) |

En Render: servicio → **Environment** → agregar la variable → **Save** (el servicio se vuelve a desplegar).

## 7. Reglas

- **Nunca** subir el `.env` ni escribir `IA_API_KEY` en el repo, en commits ni en chats grupales públicos.
- Si cambian el formato de `POST /detectar` en el repo de IA, avisar: el backend principal lee
  `clase`, `confianza`, `bbox` y `area_pct`.
- Para volver atrás un despliegue malo del backend: `git revert <commit>` y `git push origin main`.

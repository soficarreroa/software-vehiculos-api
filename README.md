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
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

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
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
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
- `GET /api/v1/cotizaciones` - Lista todas las cotizaciones
- `GET /api/v1/talleres` - Lista talleres aliados




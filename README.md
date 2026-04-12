# Software Vehiculos API

FastAPI + SUPABASE
---

## Requirements

- Python 3.13+
- MySQL or MariaDB

---

## Windows — Local Development

### 1. Install Python

Download from https://python.org/downloads

During install check **"Add Python to PATH"**.

### 2. Clone the repository

```cmd
git clone https://github.com/soficarreroa/software-vehiculos-api.git
cd software-vehiculos-api
```

### 3. Create virtual environment

```cmd
python -m venv venv
source venv/bin/activate
```

### 4. Install dependencies

```cmd
pip install fastapi uvicorn pymysql sqlalchemy supabase python-dotenv
```
### 5. Crear variables de entorno .env
## Variables de entorno

El proyecto requiere un archivo `.env` con las credenciales de la base de datos.

### Pasos

1. Copia el archivo de ejemplo:

```bash
cp .env_example .env
```

2. Abre el archivo `.env` y completa los valores:

```
SUPABASE_URL=
SUPABASE_KEY=
```

3. Pide los valores a **Sofía o Juan** — ella tiene las credenciales del proyecto.

> El archivo `.env` nunca debe subirse al repositorio. Ya está incluido en `.gitignore`.

### 6. Run the server

```cmd
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 7. Test

Open browser at `http://localhost:8000`




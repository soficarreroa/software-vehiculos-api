# Software Vehiculos API

FastAPI + MySQL/MariaDB REST API.

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
venv\Scripts\activate
```

### 4. Install dependencies

```cmd
pip install -r requirements.txt
```

### 5. Run the server

```cmd
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Test

Open browser at `http://localhost:8000`


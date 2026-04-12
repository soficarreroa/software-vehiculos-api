from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()  # must be before importing routers

from talleres_aliados import router as talleres_router

app = FastAPI()

app.include_router(talleres_router)

@app.get("/")
def root():
    return {"status": "running"}

@app.post("/vehiculos/test")
def crear_vehiculo_test():
    return {
        "id": "uuid-here",
        "marca": "Toyota",
        "modelo": "Corolla",
        "año": 2022,
        "placa": "ABC123",
        "created_at": "2026-04-12T00:00:00"
    }
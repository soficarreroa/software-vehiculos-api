from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from talleres_aliados import router as talleres_router
from vehiculos import router as vehiculos_router
from cotizaciones import router as cotizaciones_router
from piezas import router as piezas_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://software-vehiculos.vercel.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(talleres_router, prefix="/api/v1")
app.include_router(vehiculos_router, prefix="/api/v1")
app.include_router(cotizaciones_router, prefix="/api/v1")
app.include_router(piezas_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"status": "running", "message": "API funcionando correctamente"}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from talleres_aliados import router as talleres_router
from historial import router as historial_router
from vehiculos import router as vehiculos_router
from cotizaciones import router as cotizaciones_router
from piezas import router as piezas_router

app = FastAPI(title="AutoPerito API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(talleres_router, prefix="/api/v1")
app.include_router(historial_router)
app.include_router(vehiculos_router, prefix="/api/v1")
app.include_router(cotizaciones_router, prefix="/api/v1")
app.include_router(piezas_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "API AutoPerito funcionando"}

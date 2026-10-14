from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.auth import router as auth_router
from app.routers.talleres_aliados import router as talleres_router
from app.routers.historial import router as historial_router
from app.routers.vehiculos import router as vehiculos_router
from app.routers.cotizaciones import router as cotizaciones_router
from app.routers.piezas import router as piezas_router
from app.routers.piezas import router as piezas_router
from app.routers.admin import router as admin_router 

app = FastAPI(title="AutoPerito API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(talleres_router, prefix="/api/v1")
app.include_router(historial_router)
app.include_router(vehiculos_router, prefix="/api/v1")
app.include_router(cotizaciones_router, prefix="/api/v1")
app.include_router(piezas_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "API AutoPerito funcionando"}

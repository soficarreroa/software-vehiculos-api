from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from talleres_aliados import router as talleres_router
from historial import router as historial_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://software-vehiculos.vercel.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(talleres_router, prefix="/api/v1")
app.include_router(historial_router)
@app.get("/")
def root():
    return {"status": "running"}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from talleres_aliados import router as talleres_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://software-vehiculos-git-sofia-fea-e852c0-sofia-carreros-projects.vercel.app",
        "https://software-vehiculos.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(talleres_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"status": "running"}

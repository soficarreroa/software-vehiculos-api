from fastapi import APIRouter, HTTPException
from database import client

router = APIRouter()

@router.get("/talleres")
def get_talleres():
    try:
        response = client.table("talleres").select(
            "id, nombre, direccion, telefono, email, marcas_soportadas, lat, lng, certificado, notas, creado_en, categoria, rating, reviews"
        ).execute()
        return response.data
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/talleres")
def create_taller(taller: dict):
    try:
        response = client.table("talleres").insert(taller).execute()
        return response.data[0]
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))
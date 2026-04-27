from fastapi import APIRouter, HTTPException
from database import client

router = APIRouter()

@router.get("/marcas")
def get_marcas():
    try:
        response = client.table("talleres").select("marcas_soportadas").execute()
        marcas = set()
        for item in response.data:
            if item.get("marcas_soportadas"):
                marcas.update(item["marcas_soportadas"])
        return sorted(list(marcas))
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/talleres")
def get_talleres(marca: str = None):
    try:
        query = client.table("talleres").select(
            "id, nombre, direccion, telefono, email, marcas_soportadas, lat, lng, certificado, notas, creado_en, categoria, rating, reviews"
        )
        if marca:
            query = query.contains(marcas_soportadas=[marca])
        response = query.execute()
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
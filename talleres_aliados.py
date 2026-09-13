from fastapi import APIRouter, Depends, HTTPException
from database import client
from dependencies import requiere_rol

router = APIRouter()

@router.get("/marcas")
def get_marcas():
    try:
        response = client.table("talleres").select("marcas_soportadas").execute()

        # Deduplicar por minúscula: "Toyota" y "toyota" deben contar como
        # la misma marca. Se guarda la primera capitalización vista para
        # mostrarla, pero la comparación es case-insensitive.
        marcas_por_clave: dict[str, str] = {}
        for item in response.data:
            for marca in item.get("marcas_soportadas") or []:
                marca_limpia = marca.strip()
                if not marca_limpia:
                    continue
                clave = marca_limpia.lower()
                marcas_por_clave.setdefault(clave, marca_limpia)

        return sorted(marcas_por_clave.values(), key=str.lower)
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

@router.post("/talleres", dependencies=[Depends(requiere_rol(["taller"]))])
def create_taller(taller: dict):
    try:
        response = client.table("talleres").insert(taller).execute()
        return response.data[0]
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))
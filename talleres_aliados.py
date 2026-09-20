from math import radians, sin, cos, sqrt, atan2

from fastapi import APIRouter, Depends, HTTPException, Query
from database import client
from dependencies import requiere_rol

router = APIRouter()

RADIO_MAXIMO_KM = 10.0

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


def calcular_distancia_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calcula la distancia en kilómetros entre dos puntos geográficos
    usando la fórmula de Haversine (la estándar para distancias sobre
    la superficie de la Tierra a partir de latitud/longitud).
    """
    radio_tierra_km = 6371.0

    lat1_rad, lng1_rad = radians(lat1), radians(lng1)
    lat2_rad, lng2_rad = radians(lat2), radians(lng2)

    delta_lat = lat2_rad - lat1_rad
    delta_lng = lng2_rad - lng1_rad

    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lng / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return radio_tierra_km * c


@router.get("/talleres/cercanos")
def get_talleres_cercanos(
    lat: float = Query(..., description="Latitud del usuario", ge=-90, le=90),
    lng: float = Query(..., description="Longitud del usuario", ge=-180, le=180),
):
    """
    Recibe la latitud y longitud del usuario y devuelve solo los talleres
    que están a 10 km o menos de distancia, ordenados del más cercano al
    más lejano, con su distancia en kilómetros.
    """
    try:
        response = client.table("talleres").select(
            "id, nombre, direccion, telefono, email, marcas_soportadas, "
            "lat, lng, certificado, notas, creado_en, categoria, rating, reviews"
        ).execute()

        talleres_cercanos = []
        for taller in response.data:
            taller_lat = taller.get("lat")
            taller_lng = taller.get("lng")

            # Si el taller no tiene coordenadas guardadas, lo excluimos
            # en vez de romper el endpoint por un dato faltante.
            if taller_lat is None or taller_lng is None:
                continue

            distancia = calcular_distancia_km(lat, lng, taller_lat, taller_lng)

            # Filtro: solo se devuelven los talleres dentro del radio máximo.
            if distancia > RADIO_MAXIMO_KM:
                continue

            taller_con_distancia = {**taller, "distancia_km": round(distancia, 2)}
            talleres_cercanos.append(taller_con_distancia)

        talleres_cercanos.sort(key=lambda t: t["distancia_km"])

        return talleres_cercanos
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))
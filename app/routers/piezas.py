from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.core.database import client
from app.core.dependencies import get_usuario_con_rol
from app.services.catalogo_piezas import desglosar, elegir_precio, filas_por_pieza

router = APIRouter()

# Modelo para piezas disponibles para un vehículo
class PiezaDisponibleResponse(BaseModel):
    id: int
    codigo: Optional[str]
    nombre: str
    zona: Optional[str]
    descripcion: Optional[str]
    precio_repuesto: Optional[float]
    precio_mano_obra: Optional[float]
    precio_pintura: Optional[float]
    moneda: Optional[str]
    creado_en: datetime

    class Config:
        from_attributes = True

@router.get("/vehiculos/{vehiculo_id}/piezas-disponibles", response_model=List[PiezaDisponibleResponse])
def get_piezas_disponibles_vehiculo(
    vehiculo_id: int,
    usuario: dict = Depends(get_usuario_con_rol),
):
    """Obtener piezas disponibles para un vehículo específico basado en su marca y modelo"""
    try:
        # Primero obtener la información del vehículo
        vehiculo_response = (
            client.table("vehiculos")
            .select("marca, modelo")
            .eq("id", vehiculo_id)
            .eq("usuario_id", usuario["id"])
            .execute()
        )

        if not vehiculo_response.data:
            raise HTTPException(status_code=404, detail="Vehículo no encontrado")

        vehiculo = vehiculo_response.data[0]
        marca = vehiculo.get("marca")
        modelo = vehiculo.get("modelo")

        if not marca or not modelo:
            raise HTTPException(status_code=400, detail="El vehículo no tiene marca o modelo definido")

        # Piezas con precio; el precio sale de la fila que mejor coincide con el vehículo
        piezas = client.table("piezas").select(
            "id, codigo, nombre, zona, descripcion, creado_en"
        ).order("nombre").execute().data or []
        precios = filas_por_pieza(client)

        piezas_disponibles = []
        for pieza in piezas:
            # Sin precio en el catálogo la pieza igual se ofrece (con precios en 0) para
            # que el usuario pueda elegirla; antes se omitía y la lista llegaba vacía.
            fila = elegir_precio(precios.get(pieza["id"], []), marca, modelo)
            piezas_disponibles.append({**pieza, **desglosar(fila)})

        return piezas_disponibles

    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR al obtener piezas para vehículo {vehiculo_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener piezas disponibles: {str(e)}")
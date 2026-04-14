from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from database import client

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
def get_piezas_disponibles_vehiculo(vehiculo_id: int):
    """Obtener piezas disponibles para un vehículo específico basado en su marca y modelo"""
    try:
        # Primero obtener la información del vehículo
        vehiculo_response = client.table("vehiculos").select("marca, modelo").eq("id", vehiculo_id).execute()

        if not vehiculo_response.data:
            raise HTTPException(status_code=404, detail="Vehículo no encontrado")

        vehiculo = vehiculo_response.data[0]
        marca = vehiculo.get("marca")
        modelo = vehiculo.get("modelo")

        if not marca or not modelo:
            raise HTTPException(status_code=400, detail="El vehículo no tiene marca o modelo definido")

        # Obtener piezas disponibles para esta marca y modelo
        # Unimos las tablas piezas y catalogo_precios
        piezas_response = client.table("piezas").select(
            "id, codigo, nombre, zona, descripcion, creado_en"
        ).execute()

        piezas_disponibles = []

        for pieza in piezas_response.data:
            # Buscar precios para esta pieza y el vehículo
            precios = client.table("catalogo_precios").select(
                "precio_repuesto, precio_mano_obra, precio_pintura, moneda"
            ).eq("pieza_id", pieza["id"]).execute()

            # Filtrar precios que coincidan con la marca/modelo del vehículo
            precio_aplicable = None
            for precio in precios.data:
                # Aquí puedes agregar lógica más compleja de matching
                # Por ahora, solo verificamos que tenga precios definidos
                if precio.get("precio_repuesto") is not None:
                    precio_aplicable = precio
                    break

            if precio_aplicable:
                pieza_con_precio = pieza.copy()
                pieza_con_precio.update({
                    "precio_repuesto": precio_aplicable.get("precio_repuesto"),
                    "precio_mano_obra": precio_aplicable.get("precio_mano_obra"),
                    "precio_pintura": precio_aplicable.get("precio_pintura"),
                    "moneda": precio_aplicable.get("moneda", "COP")
                })
                piezas_disponibles.append(pieza_con_precio)

        return piezas_disponibles

    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR al obtener piezas para vehículo {vehiculo_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener piezas disponibles: {str(e)}")
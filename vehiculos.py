from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime
from database import client

router = APIRouter()

# Modelos Pydantic para validación
class VehicleBase(BaseModel):
    placa: str = Field(..., min_length=6, description="Placa del vehículo (mínimo 6 caracteres)")
    marca: str = Field(..., description="Marca del vehículo")
    modelo: str = Field(..., description="Modelo del vehículo")
    color: str = Field(..., description="Color del vehículo")
    extra: Optional[Dict[str, Any]] = Field(default=None, description="Datos adicionales en formato JSON")

    @validator('placa')
    def validate_placa(cls, v):
        # Convertir a mayúsculas y validar formato básico
        v = v.upper()
        if len(v) < 6:
            raise ValueError('La placa debe tener al menos 6 caracteres')
        return v

    @validator('modelo')
    def validate_modelo(cls, v):
        if not isinstance(v, str) or not v.strip():
            raise ValueError('El modelo debe ser un texto no vacío')
        return v.strip()

class VehicleCreate(VehicleBase):
    # usuario_id removido temporalmente para pruebas
    pass

class VehicleUpdate(VehicleBase):
    pass

class VehicleResponse(BaseModel):
    id: int
    placa: str
    marca: str
    modelo: str
    color: str
    extra: Optional[Dict[str, Any]] = None
    creado_en: datetime
    actualizado_en: datetime

    class Config:
        from_attributes = True

# Función auxiliar para obtener usuario (placeholder por ahora)
def get_current_user_id() -> int:
    # TODO: Implementar autenticación real
    # Por ahora retorna None para pruebas sin usuario
    return None

@router.get("/vehiculos")
def get_vehiculos():
    """Obtener todos los vehículos"""
    try:
        response = client.table("vehiculos").select(
            "id, placa, marca, modelo, color, extra, creado_en, actualizado_en"
        ).execute()
        return response.data
    except Exception as e:
        print(f"ERROR al obtener vehículos: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener vehículos: {str(e)}")

@router.get("/vehiculos/{vehicle_id}")
def get_vehiculo(vehicle_id: int):
    """Obtener un vehículo específico por ID"""
    try:
        response = client.table("vehiculos").select(
            "id, placa, marca, modelo, color, extra, creado_en, actualizado_en"
        ).eq("id", vehicle_id).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Vehículo no encontrado")

        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR al obtener vehículo {vehicle_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener vehículo: {str(e)}")

@router.post("/vehiculos")
def create_vehiculo(vehicle: VehicleCreate):
    """Crear un nuevo vehículo"""
    try:
        # Preparar datos para insertar
        vehicle_data = vehicle.dict()
        vehicle_data["usuario_id"] = 1  # Se usa un usuario de prueba para cumplir la restricción NOT NULL
        vehicle_data["creado_en"] = datetime.now().isoformat()
        vehicle_data["actualizado_en"] = datetime.now().isoformat()

        response = client.table("vehiculos").insert(vehicle_data).execute()

        if not response.data:
            raise HTTPException(status_code=400, detail="No se pudo crear el vehículo")

        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR al crear vehículo: {e}")
        raise HTTPException(
            status_code=500,
            detail=(
                f"Error al crear vehículo: {str(e)}. "
                "Asegúrate de que exista un usuario con usuario_id=1 en la tabla usuarios."
            )
        )

@router.put("/vehiculos/{vehicle_id}")
def update_vehiculo(vehicle_id: int, vehicle_update: VehicleUpdate):
    """Actualizar un vehículo existente"""
    try:
        # Verificar que el vehículo existe
        existing = client.table("vehiculos").select("id").eq("id", vehicle_id).execute()

        if not existing.data:
            raise HTTPException(status_code=404, detail="Vehículo no encontrado")

        # Preparar datos para actualizar
        update_data = vehicle_update.dict()
        update_data["actualizado_en"] = datetime.now().isoformat()

        response = client.table("vehiculos").update(update_data).eq("id", vehicle_id).execute()

        if not response.data:
            raise HTTPException(status_code=400, detail="No se pudo actualizar el vehículo")

        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR al actualizar vehículo {vehicle_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar vehículo: {str(e)}")

@router.delete("/vehiculos/{vehicle_id}")
def delete_vehiculo(vehicle_id: int):
    """Eliminar un vehículo"""
    try:
        # Verificar que el vehículo existe
        existing = client.table("vehiculos").select("id").eq("id", vehicle_id).execute()

        if not existing.data:
            raise HTTPException(status_code=404, detail="Vehículo no encontrado")

        # Eliminar el vehículo
        response = client.table("vehiculos").delete().eq("id", vehicle_id).execute()

        return {"message": "Vehículo eliminado exitosamente", "id": vehicle_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR al eliminar vehículo {vehicle_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar vehículo: {str(e)}")
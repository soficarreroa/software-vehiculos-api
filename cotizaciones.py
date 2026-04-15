from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from database import client

router = APIRouter()

# Modelo para items de cotización
class ItemCotizacionCreate(BaseModel):
    pieza_id: int = Field(..., description="ID de la pieza seleccionada")
    cantidad: int = Field(default=1, description="Cantidad")
    descripcion: Optional[str] = Field(None, description="Descripción adicional")

# Modelo para cotización completa
class CotizacionCompletaCreate(BaseModel):
    vehiculo_id: int = Field(..., description="ID del vehículo")
    fecha_incidente: str = Field(..., description="Fecha del incidente (YYYY-MM-DD)")
    observaciones: Optional[str] = Field(None, description="Observaciones del incidente")
    items: List[ItemCotizacionCreate] = Field(..., description="Lista de piezas seleccionadas")

class CotizacionResponse(BaseModel):
    id: int
    vehiculo_id: int
    estado: str
    monto_total: float
    moneda: str
    fecha_incidente: str
    observaciones: Optional[str]
    creado_en: datetime
    items_count: int  # Número de items en la cotización

    class Config:
        from_attributes = True

class CotizacionDetalleResponse(CotizacionResponse):
    items: List[Dict[str, Any]] = []  # Detalles de los items

@router.post("/cotizaciones/completa", response_model=CotizacionResponse)
def create_cotizacion_completa(data: CotizacionCompletaCreate):
    """Crear una cotización completa con vehículo e items seleccionados"""
    try:
        # Verificar que el vehículo existe y pertenece al usuario
        vehiculo = client.table("vehiculos").select("id, marca, modelo").eq("id", data.vehiculo_id).execute()
        if not vehiculo.data:
            raise HTTPException(status_code=404, detail="Vehículo no encontrado")

        # Calcular precios y subtotales para cada item
        items_procesados = []
        monto_total = 0.0

        for item in data.items:
            # Obtener información de la pieza
            pieza = client.table("piezas").select("id, nombre, zona").eq("id", item.pieza_id).execute()
            if not pieza.data:
                raise HTTPException(status_code=404, detail=f"Pieza con ID {item.pieza_id} no encontrada")

            # Obtener precios del catálogo para esta pieza y vehículo
            precios = client.table("catalogo_precios").select(
                "precio_repuesto, precio_mano_obra, precio_pintura, moneda"
            ).eq("pieza_id", item.pieza_id).execute()

            # Usar el primer precio disponible (lógica simplificada)
            precio_info = precios.data[0] if precios.data else {
                "precio_repuesto": 0.0,
                "precio_mano_obra": 0.0,
                "precio_pintura": 0.0,
                "moneda": "COP"
            }

            # Calcular subtotal
            subtotal = (
                (precio_info.get("precio_repuesto", 0.0) +
                 precio_info.get("precio_mano_obra", 0.0) +
                 precio_info.get("precio_pintura", 0.0)) * item.cantidad
            )
            monto_total += subtotal

            # Preparar item para guardar
            item_procesado = {
                "pieza_id": item.pieza_id,
                "descripcion": item.descripcion or pieza.data[0]["nombre"],
                "cantidad": item.cantidad,
                "precio_unit_repuesto": precio_info.get("precio_repuesto", 0.0),
                "precio_unit_mano_obra": precio_info.get("precio_mano_obra", 0.0),
                "precio_unit_pintura": precio_info.get("precio_pintura", 0.0),
                "subtotal": subtotal,
                "notas": f"Pieza para {vehiculo.data[0]['marca']} {vehiculo.data[0]['modelo']}",
                "creado_en": datetime.now().isoformat()
            }
            items_procesados.append(item_procesado)

        # Preparar datos de la cotización
        cotizacion_data = {
            "usuario_id": 1,  # Usuario de prueba
            "vehiculo_id": data.vehiculo_id,
            "estado": "borrador",
            "monto_total": monto_total,
            "moneda": "COP",
            "fecha_incidente": data.fecha_incidente,
            "observaciones": data.observaciones,
            "acepto_legal": True,  # Asumimos que acepta al enviar
            "creado_en": datetime.now().isoformat(),
            "actualizado_en": datetime.now().isoformat()
        }

        # Crear la cotización
        cotizacion_response = client.table("cotizaciones").insert(cotizacion_data).execute()
        if not cotizacion_response.data:
            raise HTTPException(status_code=400, detail="No se pudo crear la cotización")

        cotizacion = cotizacion_response.data[0]
        cotizacion_id = cotizacion["id"]

        # Crear los items
        for item in items_procesados:
            item["cotizacion_id"] = cotizacion_id
            client.table("items_cotizacion").insert(item).execute()

        # Preparar respuesta
        response_data = {
            "id": cotizacion_id,
            "vehiculo_id": cotizacion["vehiculo_id"],
            "estado": cotizacion["estado"],
            "monto_total": cotizacion["monto_total"],
            "moneda": cotizacion["moneda"],
            "fecha_incidente": cotizacion["fecha_incidente"],
            "observaciones": cotizacion["observaciones"],
            "creado_en": cotizacion["creado_en"],
            "items_count": len(items_procesados)
        }

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR al crear cotización completa: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear cotización completa: {str(e)}")

@router.get("/cotizaciones", response_model=List[CotizacionResponse])
def get_cotizaciones_usuario():
    """Obtener todas las cotizaciones del usuario actual"""
    try:
        # Obtener cotizaciones del usuario (usuario_id = 1 por ahora)
        cotizaciones_response = client.table("cotizaciones").select(
            "id, vehiculo_id, estado, monto_total, moneda, fecha_incidente, observaciones, creado_en"
        ).eq("usuario_id", 1).order("creado_en", desc=True).execute()

        cotizaciones = []
        for cot in cotizaciones_response.data:
            # Contar items de cada cotización
            items_count = client.table("items_cotizacion").select("id", count="exact").eq("cotizacion_id", cot["id"]).execute()
            cot["items_count"] = items_count.count or 0
            cotizaciones.append(cot)

        return cotizaciones

    except Exception as e:
        print(f"ERROR al obtener cotizaciones: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener cotizaciones: {str(e)}")

@router.get("/cotizaciones/{cotizacion_id}", response_model=CotizacionDetalleResponse)
def get_cotizacion_detalle(cotizacion_id: int):
    """Obtener detalles completos de una cotización"""
    try:
        # Obtener la cotización
        cotizacion_response = client.table("cotizaciones").select(
            "id, vehiculo_id, estado, monto_total, moneda, fecha_incidente, observaciones, creado_en"
        ).eq("id", cotizacion_id).eq("usuario_id", 1).execute()

        if not cotizacion_response.data:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")

        cotizacion = cotizacion_response.data[0]

        # Obtener los items con información de piezas
        items_response = client.table("items_cotizacion").select(
            "id, pieza_id, descripcion, cantidad, precio_unit_repuesto, precio_unit_mano_obra, precio_unit_pintura, subtotal, notas"
        ).eq("cotizacion_id", cotizacion_id).execute()

        # Enriquecer items con información de piezas
        items_detallados = []
        for item in items_response.data:
            pieza_info = client.table("piezas").select("nombre, zona").eq("id", item["pieza_id"]).execute()
            item_detallado = item.copy()
            if pieza_info.data:
                item_detallado["pieza_nombre"] = pieza_info.data[0]["nombre"]
                item_detallado["pieza_zona"] = pieza_info.data[0]["zona"]
            items_detallados.append(item_detallado)

        cotizacion["items"] = items_detallados
        cotizacion["items_count"] = len(items_detallados)

        return cotizacion

    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR al obtener cotización {cotizacion_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener cotización: {str(e)}")
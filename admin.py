from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from database import client
from dependencies import requiere_rol

router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(requiere_rol(["admin"]))],
)

ROLES_VALIDOS = {"cliente", "taller", "admin"}


class CambioRolRequest(BaseModel):
    rol: str


class CambioEstadoRequest(BaseModel):
    activo: bool


class CatalogoPrecioRequest(BaseModel):
    pieza_id: int
    marca: str
    modelo: str
    ano_desde: int
    ano_hasta: int
    precio_repuesto: float
    precio_mano_obra: float | None = None
    precio_pintura: float | None = None
    moneda: str = "COP"


@router.get("/resumen")
def get_resumen():
    """Métricas generales para las tarjetas KPI del dashboard de administrador."""
    try:
        usuarios = client.table("usuarios").select("id, rol, activo").execute().data
        talleres = client.table("talleres").select("id, verificado").execute().data
        cotizaciones = client.table("cotizaciones").select("id, estado").execute().data
        vehiculos = client.table("vehiculos").select("id").execute().data

        cotizaciones_por_estado: dict[str, int] = {}
        for c in cotizaciones:
            estado = c.get("estado") or "sin_estado"
            cotizaciones_por_estado[estado] = cotizaciones_por_estado.get(estado, 0) + 1

        return {
            "total_usuarios": len(usuarios),
            "usuarios_por_rol": {
                rol: sum(1 for u in usuarios if u.get("rol") == rol)
                for rol in {u.get("rol") for u in usuarios}
            },
            "usuarios_inactivos": sum(1 for u in usuarios if not u.get("activo", True)),
            "total_talleres": len(talleres),
            "talleres_pendientes": sum(1 for t in talleres if not t.get("verificado")),
            "total_vehiculos": len(vehiculos),
            "total_cotizaciones": len(cotizaciones),
            "cotizaciones_por_estado": cotizaciones_por_estado,
        }
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/talleres")
def get_talleres_admin():
    """Lista completa de talleres, incluidos los pendientes de aprobación."""
    try:
        response = (
            client.table("talleres")
            .select(
                "id, nombre, propietario_id, direccion, telefono, email, "
                "categoria, verificado, certificado, creado_en"
            )
            .order("creado_en", desc=True)
            .execute()
        )
        return response.data
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/talleres/{taller_id}/verificar")
def verificar_taller(taller_id: int, verificado: bool):
    """Aprueba, rechaza o revoca la verificación de un taller aliado."""
    try:
        existing = client.table("talleres").select("id").eq("id", taller_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Taller no encontrado")

        response = (
            client.table("talleres")
            .update({"verificado": verificado})
            .eq("id", taller_id)
            .execute()
        )
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/usuarios")
def get_usuarios_admin():
    """Lista completa de usuarios para la tabla de gestión de roles."""
    try:
        response = (
            client.table("usuarios")
            .select("id, correo, nombre_completo, rol, activo, creado_en")
            .order("creado_en", desc=True)
            .execute()
        )
        return response.data
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/usuarios/{usuario_id}/rol")
def cambiar_rol_usuario(usuario_id: int, payload: CambioRolRequest):
    """Reasigna el rol de un usuario (cliente, taller o admin)."""
    if payload.rol not in ROLES_VALIDOS:
        raise HTTPException(status_code=400, detail="Rol inválido")
    try:
        existing = client.table("usuarios").select("id").eq("id", usuario_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        response = (
            client.table("usuarios")
            .update({"rol": payload.rol})
            .eq("id", usuario_id)
            .execute()
        )
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/usuarios/{usuario_id}/estado")
def cambiar_estado_usuario(usuario_id: int, payload: CambioEstadoRequest):
    """Activa o desactiva la cuenta de un usuario."""
    try:
        existing = client.table("usuarios").select("id").eq("id", usuario_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        response = (
            client.table("usuarios")
            .update({"activo": payload.activo})
            .eq("id", usuario_id)
            .execute()
        )
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/piezas")
def get_piezas_admin():
    """Lista de piezas existentes, para el selector del catálogo de precios."""
    try:
        response = (
            client.table("piezas")
            .select("id, codigo, nombre, zona, descripcion")
            .order("nombre")
            .execute()
        )
        return response.data
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalogo-precios")
def get_catalogo_precios():
    """Lista completa del catálogo de precios, con el nombre de la pieza incluido."""
    try:
        precios = (
            client.table("catalogo_precios")
            .select(
                "id, pieza_id, marca, modelo, ano_desde, ano_hasta, "
                "precio_repuesto, precio_mano_obra, precio_pintura, moneda"
            )
            .order("id", desc=True)
            .execute()
        ).data

        piezas = client.table("piezas").select("id, nombre, codigo").execute().data
        nombres_pieza = {p["id"]: p["nombre"] for p in piezas}

        for precio in precios:
            precio["pieza_nombre"] = nombres_pieza.get(precio["pieza_id"], "Pieza desconocida")

        return precios
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/catalogo-precios", status_code=status.HTTP_201_CREATED)
def crear_precio_catalogo(payload: CatalogoPrecioRequest):
    """Asigna un precio a una pieza para un rango de marca/modelo/año."""
    try:
        pieza_existe = client.table("piezas").select("id").eq("id", payload.pieza_id).execute()
        if not pieza_existe.data:
            raise HTTPException(status_code=404, detail="Pieza no encontrada")

        response = client.table("catalogo_precios").insert(payload.model_dump()).execute()
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/catalogo-precios/{precio_id}")
def eliminar_precio_catalogo(precio_id: int):
    """Elimina una entrada del catálogo de precios."""
    try:
        existing = client.table("catalogo_precios").select("id").eq("id", precio_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Registro no encontrado")

        client.table("catalogo_precios").delete().eq("id", precio_id).execute()
        return {"eliminado": True, "id": precio_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))
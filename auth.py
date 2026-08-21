from types import SimpleNamespace
from typing import Any

import bcrypt
from fastapi import APIRouter, HTTPException, status
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from database import client

if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = SimpleNamespace(__version__=getattr(bcrypt, "__version__", "4.1.2"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter(prefix="/auth", tags=["auth"])


def hash_password(password: str) -> str:
    """Genera un hash seguro con bcrypt para almacenar contraseñas."""
    if not password or not password.strip():
        raise ValueError("La contraseña no puede estar vacía")
    if len(password.encode("utf-8")) > 72:
        raise ValueError("La contraseña excede el máximo permitido por bcrypt (72 bytes)")
    return pwd_context.hash(password)


def normalize_email(email: str) -> str:
    """Normaliza email para evitar espacios y formato inválido antes de crear el usuario en Auth."""
    if not isinstance(email, str):
        raise ValueError("El correo debe ser un texto válido")
    normalized = email.strip().lower()
    if not normalized:
        raise ValueError("El correo no puede estar vacío")
    return normalized


class ClienteRegisterSchema(BaseModel):
    nombre_completo: str = Field(..., min_length=2, description="Nombre completo del cliente")
    correo: EmailStr = Field(..., description="Correo electrónico del cliente")
    telefono: str = Field(..., min_length=7, description="Teléfono del cliente")
    contrasena: str = Field(..., min_length=8, max_length=72, description="Contraseña del cliente")
    confirmar_contrasena: str = Field(..., min_length=8, max_length=72, description="Confirmación de la contraseña")

    placa: str | None = Field(default=None, description="Placa del vehículo")
    marca: str | None = Field(default=None, description="Marca del vehículo")
    modelo: str | None = Field(default=None, description="Modelo del vehículo")
    color: str | None = Field(default=None, description="Color del vehículo")
    anio_fabricacion: int | None = Field(default=None, ge=1900, le=2100)
    tipo_carroceria: str | None = Field(default=None)
    detalles_equipamiento: str | None = Field(default=None)

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @field_validator("nombre_completo", "telefono", "marca", "modelo", "color", "tipo_carroceria")
    @classmethod
    def clean_required_strings(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Este campo no puede quedar vacío")
        return normalized

    @field_validator("placa")
    @classmethod
    def normalize_placa(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("La placa no puede quedar vacía")
        return normalized

    @model_validator(mode="after")
    def validate_passwords_and_vehicle_data(self) -> "ClienteRegisterSchema":
        if self.contrasena != self.confirmar_contrasena:
            raise ValueError("Las contraseñas no coinciden")

        vehicle_fields = [self.placa, self.marca, self.modelo, self.color, self.tipo_carroceria, self.detalles_equipamiento]
        has_vehicle_data = any(value is not None and str(value).strip() not in ("", "None") for value in vehicle_fields)
        if has_vehicle_data and not self.placa:
            raise ValueError("Si se envían datos del vehículo, la placa es obligatoria")

        return self


class TallerRegisterSchema(BaseModel):
    nombre_representante: str = Field(..., min_length=2, description="Nombre del representante legal")
    correo_corporativo: EmailStr = Field(..., description="Correo corporativo")
    contrasena: str = Field(..., min_length=8, max_length=72, description="Contraseña del representante")
    confirmar_contrasena: str = Field(..., min_length=8, max_length=72, description="Confirmación de la contraseña")

    nombre_comercial: str = Field(..., min_length=2, description="Nombre comercial del taller")
    telefono_taller: str = Field(..., min_length=7, description="Teléfono del taller")
    categoria_especialidad: str = Field(..., min_length=2, description="Categoría o especialidad del taller")
    direccion_fisica: str = Field(..., min_length=5, description="Dirección física del taller")
    marcas_soportadas: list[str] = Field(..., min_length=1, description="Marcas soportadas por el taller")
    notas_servicios: str | None = Field(default=None, description="Notas o servicios ofrecidos")

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @field_validator(
        "nombre_representante",
        "nombre_comercial",
        "categoria_especialidad",
        "direccion_fisica",
        "telefono_taller",
    )
    @classmethod
    def clean_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Este campo no puede quedar vacío")
        return normalized

    @field_validator("marcas_soportadas")
    @classmethod
    def validate_marcas_soportadas(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("Debe indicar al menos una marca soportada")
        cleaned = []
        for marca in value:
            if not isinstance(marca, str):
                raise ValueError("Cada marca debe ser texto")
            normalized = marca.strip()
            if not normalized:
                continue
            cleaned.append(normalized)
        if not cleaned:
            raise ValueError("Debe indicar al menos una marca soportada")
        return cleaned

    @model_validator(mode="after")
    def validate_passwords_match(self) -> "TallerRegisterSchema":
        if self.contrasena != self.confirmar_contrasena:
            raise ValueError("Las contraseñas no coinciden")
        return self


def _build_vehicle_extra(payload: ClienteRegisterSchema) -> dict[str, Any] | None:
    extra: dict[str, Any] = {}

    if payload.anio_fabricacion is not None:
        extra["anio_fabricacion"] = payload.anio_fabricacion
    if payload.tipo_carroceria:
        extra["tipo_carroceria"] = payload.tipo_carroceria.strip()
    if payload.detalles_equipamiento:
        extra["detalles_equipamiento"] = payload.detalles_equipamiento.strip()

    return extra or None


@router.post("/registro/cliente", status_code=status.HTTP_201_CREATED)
def register_cliente(payload: ClienteRegisterSchema):
    try:
        email = normalize_email(str(payload.correo))
        password = payload.contrasena.strip()

        auth_response = client.auth.sign_up({
            "email": email,
            "password": password,
        })

        if not getattr(auth_response, "user", None) or not getattr(auth_response.user, "id", None):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo crear el usuario en Supabase Auth",
            )

        auth_id = str(auth_response.user.id)
        hashed_password = hash_password(password)

        usuario_payload = {
            "correo": email,
            "nombre_completo": payload.nombre_completo.strip(),
            "telefono": payload.telefono.strip(),
            "clave_hash": hashed_password,
            "rol": "cliente",
            "auth_id": auth_id,
            "activo": True,
        }

        usuario_result = client.table("usuarios").insert(usuario_payload).execute()
        if not usuario_result.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudo crear el usuario cliente")

        usuario_creado = usuario_result.data[0]
        usuario_id = usuario_creado.get("id")

        vehiculo_data = None
        if payload.placa:
            vehiculo_payload = {
                "usuario_id": usuario_id,
                "placa": payload.placa,
                "marca": payload.marca,
                "modelo": payload.modelo,
                "color": payload.color,
                "extra": _build_vehicle_extra(payload),
            }
            vehiculo_result = client.table("vehiculos").insert(vehiculo_payload).execute()
            if not vehiculo_result.data:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudo crear el vehículo asociado")
            vehiculo_data = vehiculo_result.data[0]

        return {
            "message": "Cliente registrado correctamente",
            "usuario": {
                "id": usuario_creado.get("id"),
                "correo": usuario_creado.get("correo"),
                "nombre_completo": usuario_creado.get("nombre_completo"),
                "rol": usuario_creado.get("rol"),
                "auth_id": usuario_creado.get("auth_id"),
                "activo": usuario_creado.get("activo"),
            },
            "vehiculo": vehiculo_data,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar cliente: {str(exc)}",
        ) from exc


@router.post("/registro/taller", status_code=status.HTTP_201_CREATED)
def register_taller(payload: TallerRegisterSchema):
    try:
        email = normalize_email(str(payload.correo_corporativo))
        password = payload.contrasena.strip()

        auth_response = client.auth.sign_up({
            "email": email,
            "password": password,
        })

        if not getattr(auth_response, "user", None) or not getattr(auth_response.user, "id", None):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo crear el usuario en Supabase Auth",
            )

        auth_id = str(auth_response.user.id)
        hashed_password = hash_password(password)

        usuario_payload = {
            "correo": email,
            "nombre_completo": payload.nombre_representante.strip(),
            "telefono": payload.telefono_taller.strip(),
            "clave_hash": hashed_password,
            "rol": "taller",
            "auth_id": auth_id,
            "activo": True,
        }

        usuario_result = client.table("usuarios").insert(usuario_payload).execute()
        if not usuario_result.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudo crear el usuario taller")

        usuario_creado = usuario_result.data[0]
        taller_payload = {
            "propietario_id": auth_id,
            "nombre": payload.nombre_comercial,
            "direccion": payload.direccion_fisica,
            "telefono": payload.telefono_taller,
            "email": payload.correo_corporativo,
            "marcas_soportadas": payload.marcas_soportadas,
            "categoria": payload.categoria_especialidad,
            "notas": payload.notas_servicios,
            "verificado": False,
        }

        taller_result = client.table("talleres").insert(taller_payload).execute()
        if not taller_result.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudo crear el taller asociado")

        taller_creado = taller_result.data[0]

        return {
            "message": "Taller registrado correctamente",
            "usuario": {
                "id": usuario_creado.get("id"),
                "correo": usuario_creado.get("correo"),
                "nombre_completo": usuario_creado.get("nombre_completo"),
                "rol": usuario_creado.get("rol"),
                "auth_id": usuario_creado.get("auth_id"),
                "activo": usuario_creado.get("activo"),
            },
            "taller": {
                "id": taller_creado.get("id"),
                "propietario_id": taller_creado.get("propietario_id"),
                "nombre": taller_creado.get("nombre"),
                "email": taller_creado.get("email"),
                "categoria": taller_creado.get("categoria"),
                "verificado": taller_creado.get("verificado"),
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar taller: {str(exc)}",
        ) from exc

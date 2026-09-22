from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class EmpleadoPublico(BaseModel):
    id: int
    nombre: str
    apellido: str

    class Config:
        from_attributes = True

class MarcajeCreate(BaseModel):
    token: str
    tipo_marca: str # "ENTRADA" o "SALIDA"
    empleado_id: Optional[int] = None
    pin: Optional[str] = None
    es_nuevo: bool = False
    nombre_completo: Optional[str] = None
    cedula: Optional[str] = None

class MarcajeRespuesta(BaseModel):
    estado: str
    mensaje: str
    empleado: str
    hora_entrada: Optional[datetime] = None
    hora_salida: Optional[datetime] = None
    horas_trabajadas: Optional[float] = None
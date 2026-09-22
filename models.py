from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Empleado(Base):
    __tablename__ = "empleados"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    cedula = Column(String(20), unique=True, nullable=True)
    pin_hash = Column(String(255), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    creado_el = Column(DateTime, default=datetime.utcnow)

    asistencias = relationship("Asistencia", back_populates="empleado")

class CartelQR(Base):
    __tablename__ = "carteles_qr"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    descripcion = Column(String(100), default="Cartel Entrada Principal")
    activo = Column(Boolean, default=True, nullable=False)
    creado_el = Column(DateTime, default=datetime.utcnow)

    asistencias = relationship("Asistencia", back_populates="cartel_qr")

class Asistencia(Base):
    __tablename__ = "asistencias"

    id = Column(Integer, primary_key=True, index=True)
    empleado_id = Column(Integer, ForeignKey("empleados.id"), nullable=False)
    cartel_qr_id = Column(Integer, ForeignKey("carteles_qr.id"), nullable=False)
    fecha = Column(Date, nullable=False, default=date.today)
    hora_entrada = Column(DateTime, nullable=False)
    hora_salida = Column(DateTime, nullable=True)
    horas_trabajadas = Column(Numeric(5, 2), nullable=True)
    ip_origen = Column(String(45), nullable=True)
    creado_el = Column(DateTime, default=datetime.utcnow)

    empleado = relationship("Empleado", back_populates="asistencias")
    cartel_qr = relationship("CartelQR", back_populates="asistencias")
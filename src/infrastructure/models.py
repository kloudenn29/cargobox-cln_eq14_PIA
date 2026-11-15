"""Modelos de Mapeo Objeto-Relacional (SQLAlchemy ORM) para CargoBox."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from src.infrastructure.database import Base


class ActorModel(Base):
    """Tabla de Actores / Remitentes."""
    __tablename__ = "actores"

    actor_id = Column(String(50), primary_key=True, index=True)
    nombre = Column(String(120), nullable=False)
    es_preferente = Column(Boolean, default=False)
    activo = Column(Boolean, default=True)
    ciudad = Column(String(80), default="Monterrey")

    operaciones = relationship("OperacionModel", back_populates="actor")


class RecursoModel(Base):
    """Tabla de Catálogo de Servicios y Tipos de Paquete."""
    __tablename__ = "catalogo"

    recurso_id = Column(String(50), primary_key=True, index=True)
    descripcion = Column(String(200), nullable=False)
    precio_mxn = Column(Numeric(10, 2), nullable=False)
    capacidad_o_stock = Column(Integer, default=0)
    habilitado = Column(Boolean, default=True)


class OperacionModel(Base):
    """Tabla de Transacciones Operativas."""
    __tablename__ = "operaciones"

    operacion_id = Column(String(50), primary_key=True, index=True)
    actor_id = Column(String(50), ForeignKey("actores.actor_id"), nullable=False)
    estado = Column(String(30), default="RECIBIDO")
    fecha_solicitud = Column(String(20), nullable=False)
    promocion_activa = Column(Boolean, default=False)
    autorizado = Column(Boolean, default=True)
    referencia = Column(String(100), default="")
    total = Column(Numeric(10, 2), default=0.00)

    actor = relationship("ActorModel", back_populates="operaciones")
    detalles = relationship("DetalleOperacionModel", back_populates="operacion", cascade="all, delete-orphan")


class DetalleOperacionModel(Base):
    """Tabla de Líneas de Detalle de Operación."""
    __tablename__ = "detalle_operaciones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operacion_id = Column(String(50), ForeignKey("operaciones.operacion_id"), nullable=False)
    recurso_id = Column(String(50), ForeignKey("catalogo.recurso_id"), nullable=False)
    cantidad = Column(Integer, nullable=False, default=1)
    precio_unitario = Column(Numeric(10, 2), default=0.00)

    operacion = relationship("OperacionModel", back_populates="detalles")
    recurso = relationship("RecursoModel")


class EnvioModel(Base):
    """Tabla de Envíos de Paquetería de CargoBox."""
    __tablename__ = "envios"

    guia = Column(String(60), primary_key=True, index=True)
    remitente_id = Column(String(50), nullable=False)
    destinatario_nombre = Column(String(120), nullable=False)

    # Dirección de Origen
    calle_origen = Column(String(100), nullable=False)
    numero_origen = Column(String(20), nullable=False)
    colonia_origen = Column(String(80), default="")
    ciudad_origen = Column(String(80), nullable=False)
    cp_origen = Column(String(10), nullable=False)

    # Dirección de Destino
    calle_destino = Column(String(100), nullable=False)
    numero_destino = Column(String(20), nullable=False)
    colonia_destino = Column(String(80), default="")
    ciudad_destino = Column(String(80), nullable=False)
    cp_destino = Column(String(10), nullable=False)

    # Paquete
    peso_kg = Column(Numeric(8, 2), nullable=False)
    largo_cm = Column(Numeric(8, 2), default=30.00)
    ancho_cm = Column(Numeric(8, 2), default=20.00)
    alto_cm = Column(Numeric(8, 2), default=15.00)
    descripcion_paquete = Column(String(200), default="Paquete general")

    # Seguro y Flete
    seguro_amparado = Column(Boolean, default=False)
    valor_declarado = Column(Numeric(10, 2), default=0.00)
    flete_monto = Column(Numeric(10, 2), default=350.00)

    # Control de Estado y Logística
    estado = Column(String(30), default="RECIBIDO")
    intentos_entrega = Column(Integer, default=0)
    cedis_actual = Column(String(60), default="CEDIS-ORIGEN-MTY")
    fecha_creacion = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class IncidenciaModel(Base):
    """Tabla de Incidencias Operativas."""
    __tablename__ = "incidencias"

    incidencia_id = Column(String(60), primary_key=True, index=True)
    guia = Column(String(60), ForeignKey("envios.guia"), nullable=False)
    tipo = Column(String(40), nullable=False)
    descripcion = Column(Text, nullable=False)
    fecha_reporte = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resuelta = Column(Boolean, default=False)
    evidencia_id = Column(String(120), default="")


class HistorialEnvioModel(Base):
    """Tabla de historial de rastreo: un renglón por cada cambio de estado del envío."""
    __tablename__ = "historial_envio"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guia = Column(String(60), ForeignKey("envios.guia"), nullable=False, index=True)
    estado = Column(String(30), nullable=False)
    detalle = Column(Text, default="")
    fecha = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class EventoLogModel(Base):
    """Tabla de Registro de Auditoría de Eventos de Dominio."""
    __tablename__ = "eventos_log"

    event_id = Column(String(60), primary_key=True)
    aggregate_id = Column(String(60), index=True)
    event_type = Column(String(80), nullable=False)
    occurred_on = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    payload = Column(Text, default="{}")


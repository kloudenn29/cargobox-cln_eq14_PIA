"""Implementaciones de Repositorios con SQLAlchemy para CargoBox."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.domain.entities import (
    Actor,
    DetalleOperacion,
    Envio,
    Incidencia,
    MovimientoEnvio,
    Operacion,
    Paquete,
    Recurso,
)
from src.domain.enums import EstadoEnvio, EstadoOperacion, TipoIncidencia
from src.domain.value_objects import Dimensiones, Dinero, Direccion, GuiaRastreo, Seguro
from src.infrastructure.models import (
    ActorModel,
    DetalleOperacionModel,
    EnvioModel,
    HistorialEnvioModel,
    IncidenciaModel,
    OperacionModel,
    RecursoModel,
)


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Las columnas DateTime se guardan sin zona horaria (UTC); al leer se restaura tzinfo."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SqlActorRepository:
    """Repositorio relacional para la entidad Actor."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, actor_id: str) -> Optional[Actor]:
        m = self.session.query(ActorModel).filter(ActorModel.actor_id == actor_id).first()
        if not m:
            return None
        return Actor(
            actor_id=m.actor_id,
            nombre=m.nombre,
            es_preferente=m.es_preferente,
            activo=m.activo,
            ciudad=m.ciudad,
        )

    def save(self, actor: Actor) -> None:
        m = self.session.query(ActorModel).filter(ActorModel.actor_id == actor.actor_id).first()
        if not m:
            m = ActorModel(actor_id=actor.actor_id)
            self.session.add(m)
        m.nombre = actor.nombre
        m.es_preferente = actor.es_preferente
        m.activo = actor.activo
        m.ciudad = actor.ciudad

    def list_all(self) -> List[Actor]:
        models = self.session.query(ActorModel).all()
        return [
            Actor(
                actor_id=m.actor_id,
                nombre=m.nombre,
                es_preferente=m.es_preferente,
                activo=m.activo,
                ciudad=m.ciudad,
            )
            for m in models
        ]


class SqlCatalogoRepository:
    """Repositorio relacional para el Catálogo de Recursos/Servicios."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, recurso_id: str) -> Optional[Recurso]:
        m = self.session.query(RecursoModel).filter(RecursoModel.recurso_id == recurso_id).first()
        if not m:
            return None
        return Recurso(
            recurso_id=m.recurso_id,
            descripcion=m.descripcion,
            precio_mxn=Decimal(str(m.precio_mxn)),
            capacidad_o_stock=m.capacidad_o_stock,
            habilitado=m.habilitado,
        )

    def save(self, recurso: Recurso) -> None:
        m = self.session.query(RecursoModel).filter(RecursoModel.recurso_id == recurso.recurso_id).first()
        if not m:
            m = RecursoModel(recurso_id=recurso.recurso_id)
            self.session.add(m)
        m.descripcion = recurso.descripcion
        m.precio_mxn = recurso.precio_mxn
        m.capacidad_o_stock = recurso.capacidad_o_stock
        m.habilitado = recurso.habilitado

    def list_all(self) -> List[Recurso]:
        models = self.session.query(RecursoModel).all()
        return [
            Recurso(
                recurso_id=m.recurso_id,
                descripcion=m.descripcion,
                precio_mxn=Decimal(str(m.precio_mxn)),
                capacidad_o_stock=m.capacidad_o_stock,
                habilitado=m.habilitado,
            )
            for m in models
        ]


class SqlOperacionRepository:
    """Repositorio relacional con soporte transaccional para el Agregado Operacion."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, operacion_id: str) -> Optional[Operacion]:
        m = self.session.query(OperacionModel).filter(OperacionModel.operacion_id == operacion_id).first()
        if not m:
            return None

        actor_repo = SqlActorRepository(self.session)
        actor = actor_repo.get_by_id(m.actor_id)

        detalles: List[DetalleOperacion] = []
        for d in m.detalles:
            detalles.append(
                DetalleOperacion(
                    operacion_id=d.operacion_id,
                    recurso_id=d.recurso_id,
                    cantidad=d.cantidad,
                    precio_unitario=Decimal(str(d.precio_unitario)),
                )
            )

        op = Operacion(
            operacion_id=m.operacion_id,
            actor_id=m.actor_id,
            estado=EstadoOperacion(m.estado),
            fecha_solicitud=m.fecha_solicitud,
            promocion_activa=m.promocion_activa,
            autorizado=m.autorizado,
            referencia=m.referencia,
            actor=actor,
            detalles=detalles,
        )
        return op

    def save(self, op: Operacion) -> None:
        m = self.session.query(OperacionModel).filter(OperacionModel.operacion_id == op.operacion_id).first()
        if not m:
            m = OperacionModel(operacion_id=op.operacion_id)
            self.session.add(m)

        m.actor_id = op.actor_id
        m.estado = op.estado.value
        m.fecha_solicitud = op.fecha_solicitud
        m.promocion_activa = op.promocion_activa
        m.autorizado = op.autorizado
        m.referencia = op.referencia
        m.total = op.calcular_total()

        # Actualizar detalles
        self.session.query(DetalleOperacionModel).filter(DetalleOperacionModel.operacion_id == op.operacion_id).delete()
        for d in op.detalles:
            dm = DetalleOperacionModel(
                operacion_id=op.operacion_id,
                recurso_id=d.recurso_id,
                cantidad=d.cantidad,
                precio_unitario=d.precio_unitario,
            )
            self.session.add(dm)

    def list_all(self) -> List[Operacion]:
        models = self.session.query(OperacionModel).all()
        return [self.get_by_id(m.operacion_id) for m in models if self.get_by_id(m.operacion_id)]

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()


class SqlEnvioRepository:
    """Repositorio relacional con soporte transaccional para el Agregado Envio."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_guia(self, guia_codigo: str) -> Optional[Envio]:
        m = self.session.query(EnvioModel).filter(EnvioModel.guia == guia_codigo).first()
        if not m:
            return None

        dir_origen = Direccion(
            calle=m.calle_origen,
            numero=m.numero_origen,
            colonia=m.colonia_origen,
            ciudad=m.ciudad_origen,
            codigo_postal=m.cp_origen,
        )
        dir_destino = Direccion(
            calle=m.calle_destino,
            numero=m.numero_destino,
            colonia=m.colonia_destino,
            ciudad=m.ciudad_destino,
            codigo_postal=m.cp_destino,
        )
        dim = Dimensiones(
            largo_cm=Decimal(str(m.largo_cm)),
            ancho_cm=Decimal(str(m.ancho_cm)),
            alto_cm=Decimal(str(m.alto_cm)),
        )
        paq = Paquete(
            peso_kg=Decimal(str(m.peso_kg)),
            dimensiones=dim,
            descripcion=m.descripcion_paquete,
        )
        seg = Seguro(
            amparado=m.seguro_amparado,
            valor_declarado=Decimal(str(m.valor_declarado)),
        )
        envio = Envio(
            guia=GuiaRastreo(m.guia),
            remitente_id=m.remitente_id,
            destinatario_nombre=m.destinatario_nombre,
            direccion_origen=dir_origen,
            direccion_destino=dir_destino,
            paquete=paq,
            seguro=seg,
            flete=Dinero(Decimal(str(m.flete_monto))),
            estado=EstadoEnvio(m.estado),
            intentos_entrega=m.intentos_entrega,
            cedis_actual=m.cedis_actual,
            fecha_creacion=_utc(m.fecha_creacion),
        )
        envio.historial = [
            MovimientoEnvio(EstadoEnvio(h.estado), h.detalle or "", _utc(h.fecha))
            for h in self.session.query(HistorialEnvioModel)
            .filter(HistorialEnvioModel.guia == guia_codigo)
            .order_by(HistorialEnvioModel.id)
            .all()
        ]
        envio.incidencias = [
            Incidencia(
                incidencia_id=i.incidencia_id,
                guia=i.guia,
                tipo=TipoIncidencia(i.tipo),
                descripcion=i.descripcion,
                fecha_reporte=_utc(i.fecha_reporte),
                resuelta=i.resuelta,
                evidencia_id=i.evidencia_id or "",
            )
            for i in self.session.query(IncidenciaModel)
            .filter(IncidenciaModel.guia == guia_codigo)
            .order_by(IncidenciaModel.fecha_reporte, IncidenciaModel.incidencia_id)
            .all()
        ]
        return envio

    def existe(self, guia_codigo: str) -> bool:
        return (
            self.session.query(EnvioModel.guia).filter(EnvioModel.guia == guia_codigo).first()
            is not None
        )

    def save(self, envio: Envio) -> None:
        m = self.session.query(EnvioModel).filter(EnvioModel.guia == envio.guia.codigo).first()
        if not m:
            m = EnvioModel(guia=envio.guia.codigo)
            self.session.add(m)

        m.remitente_id = envio.remitente_id
        m.destinatario_nombre = envio.destinatario_nombre

        m.calle_origen = envio.direccion_origen.calle
        m.numero_origen = envio.direccion_origen.numero
        m.colonia_origen = envio.direccion_origen.colonia
        m.ciudad_origen = envio.direccion_origen.ciudad
        m.cp_origen = envio.direccion_origen.codigo_postal

        m.calle_destino = envio.direccion_destino.calle
        m.numero_destino = envio.direccion_destino.numero
        m.colonia_destino = envio.direccion_destino.colonia
        m.ciudad_destino = envio.direccion_destino.ciudad
        m.cp_destino = envio.direccion_destino.codigo_postal

        m.peso_kg = envio.paquete.peso_kg
        m.largo_cm = envio.paquete.dimensiones.largo_cm
        m.ancho_cm = envio.paquete.dimensiones.ancho_cm
        m.alto_cm = envio.paquete.dimensiones.alto_cm
        m.descripcion_paquete = envio.paquete.descripcion

        m.seguro_amparado = envio.seguro.amparado
        m.valor_declarado = envio.seguro.valor_declarado
        m.flete_monto = envio.flete.monto

        m.estado = envio.estado.value
        m.intentos_entrega = envio.intentos_entrega
        m.cedis_actual = envio.cedis_actual
        m.fecha_creacion = envio.fecha_creacion
        self.session.flush()  # el envío debe existir antes de insertar historial e incidencias (FK)

        # Historial e incidencias son append-only: solo se insertan las entradas nuevas.
        guardados = self.session.query(HistorialEnvioModel).filter(
            HistorialEnvioModel.guia == envio.guia.codigo
        ).count()
        for mov in envio.historial[guardados:]:
            self.session.add(
                HistorialEnvioModel(
                    guia=envio.guia.codigo,
                    estado=mov.estado.value,
                    detalle=mov.detalle,
                    fecha=mov.fecha,
                )
            )
        ya_registradas = {
            i[0]
            for i in self.session.query(IncidenciaModel.incidencia_id)
            .filter(IncidenciaModel.guia == envio.guia.codigo)
            .all()
        }
        for inc in envio.incidencias:
            if inc.incidencia_id not in ya_registradas:
                self.session.add(
                    IncidenciaModel(
                        incidencia_id=inc.incidencia_id,
                        guia=inc.guia,
                        tipo=inc.tipo.value,
                        descripcion=inc.descripcion,
                        fecha_reporte=inc.fecha_reporte,
                        resuelta=inc.resuelta,
                        evidencia_id=inc.evidencia_id,
                    )
                )

    def list_all(self) -> List[Envio]:
        guias = [g[0] for g in self.session.query(EnvioModel.guia).all()]
        return [e for e in (self.get_by_guia(g) for g in guias) if e]

    def contar_incidencias_por_tipo(self) -> Dict[str, int]:
        """US15: agrupa las incidencias registradas por tipo (consulta GROUP BY en la BD)."""
        filas = (
            self.session.query(IncidenciaModel.tipo, func.count(IncidenciaModel.incidencia_id))
            .group_by(IncidenciaModel.tipo)
            .all()
        )
        return {tipo: total for tipo, total in filas}

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()


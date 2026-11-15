"""Servicios de Aplicación (Casos de Uso) de CargoBox."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from src.application.dtos import (
    AlertaRastreoDTO,
    DictamenIndemnizacionResponseDTO,
    EnvioCreateDTO,
    EnvioResponseDTO,
    EvaluacionReglaResponseDTO,
    IncidenciaResponseDTO,
    MovimientoDTO,
    OperacionCreateDTO,
    OperacionResponseDTO,
    RastreoResponseDTO,
    ReporteEntregasATiempoDTO,
    ReporteIncidenciasDTO,
    TransicionResponseDTO,
)
from src.domain.entities import (
    SLA_ENTREGA_HORAS,
    DetalleOperacion,
    Envio,
    Operacion,
    Paquete,
)
from src.domain.enums import EstadoEnvio, EstadoOperacion, RolUsuario, TipoIncidencia
from src.domain.exceptions import (
    DomainException,
    EntidadNoEncontradaException,
    GuiaDuplicadaException,
)
from src.domain.specifications import BeneficioReferenciaSpecification, PuedeProcesarseSpecification
from src.domain.value_objects import Dimensiones, Direccion, Seguro
from src.infrastructure.external_services import (
    ICentroDistribucionService,
    INotificacionService,
    MockCentroDistribucionService,
    MockNotificacionService,
)
from src.infrastructure.repositories import (
    SqlActorRepository,
    SqlCatalogoRepository,
    SqlEnvioRepository,
    SqlOperacionRepository,
)


class OperacionAppService:
    """Caso de uso para gestión y evaluación de operaciones comerciales del dataset."""

    def __init__(self, op_repo: SqlOperacionRepository, actor_repo: SqlActorRepository, cat_repo: SqlCatalogoRepository):
        self.op_repo = op_repo
        self.actor_repo = actor_repo
        self.cat_repo = cat_repo
        self.spec_puede_procesarse = PuedeProcesarseSpecification()
        self.spec_beneficio = BeneficioReferenciaSpecification()

    def get_operacion(self, operacion_id: str) -> Operacion:
        op = self.op_repo.get_by_id(operacion_id)
        if not op:
            raise EntidadNoEncontradaException("Operación", operacion_id)
        return op

    def crear_operacion(self, dto: OperacionCreateDTO) -> OperacionResponseDTO:
        actor = self.actor_repo.get_by_id(dto.actor_id)
        if not actor:
            raise EntidadNoEncontradaException("Actor/Remitente", dto.actor_id)

        detalles: List[DetalleOperacion] = []
        for d in dto.detalles:
            rec = self.cat_repo.get_by_id(d.recurso_id)
            precio = rec.precio_mxn if rec else d.precio_unitario
            detalles.append(
                DetalleOperacion(
                    operacion_id=dto.operacion_id,
                    recurso_id=d.recurso_id,
                    cantidad=d.cantidad,
                    precio_unitario=precio,
                    recurso=rec,
                )
            )

        op = Operacion(
            operacion_id=dto.operacion_id,
            actor_id=dto.actor_id,
            estado=EstadoOperacion.RECIBIDO,
            promocion_activa=dto.promocion_activa,
            autorizado=dto.autorizado,
            referencia=dto.referencia,
            actor=actor,
            detalles=detalles,
        )
        self.op_repo.save(op)
        self.op_repo.commit()
        return self._to_response_dto(op)

    def evaluar_precondiciones(self, operacion_id: str) -> EvaluacionReglaResponseDTO:
        op = self.get_operacion(operacion_id)
        cumple = self.spec_puede_procesarse.is_satisfied_by(op)
        explicacion = self.spec_puede_procesarse.explain(op)
        return EvaluacionReglaResponseDTO(
            operacion_id=operacion_id,
            regla="puede_procesarse (cliente activo AND detalle no vacío AND autorización)",
            cumple=cumple,
            explicacion=explicacion,
        )

    def evaluar_beneficio(self, operacion_id: str) -> EvaluacionReglaResponseDTO:
        op = self.get_operacion(operacion_id)
        cumple = self.spec_beneficio.is_satisfied_by(op)
        explicacion = self.spec_beneficio.explain(op)
        return EvaluacionReglaResponseDTO(
            operacion_id=operacion_id,
            regla="beneficio_referencia (VIP AND total >= 1500 MXN AND NOT promoción)",
            cumple=cumple,
            explicacion=explicacion,
        )

    def ejecutar_transicion(self, operacion_id: str, accion: str) -> TransicionResponseDTO:
        op = self.get_operacion(operacion_id)
        estado_ant = op.estado.value
        try:
            nuevo_est = op.transicionar(accion)
            self.op_repo.save(op)
            self.op_repo.commit()
            return TransicionResponseDTO(
                operacion_id=operacion_id,
                accion_ejecutada=accion,
                estado_anterior=estado_ant,
                estado_nuevo=nuevo_est.value,
                mensaje="Transición ejecutada exitosamente.",
            )
        except Exception:
            self.op_repo.rollback()
            raise

    def _to_response_dto(self, op: Operacion) -> OperacionResponseDTO:
        return OperacionResponseDTO(
            operacion_id=op.operacion_id,
            actor_id=op.actor_id,
            estado=op.estado.value,
            fecha_solicitud=op.fecha_solicitud,
            promocion_activa=op.promocion_activa,
            autorizado=op.autorizado,
            referencia=op.referencia,
            total_mxn=op.calcular_total(),
            detalles_count=len(op.detalles),
        )


class EnvioAppService:
    """Caso de uso para el ciclo logístico integral de envíos de CargoBox."""

    def __init__(
        self,
        envio_repo: SqlEnvioRepository,
        cedis_service: Optional[ICentroDistribucionService] = None,
        notificacion_service: Optional[INotificacionService] = None,
    ):
        self.envio_repo = envio_repo
        self.cedis_service = cedis_service or MockCentroDistribucionService()
        self.notificacion_service = notificacion_service or MockNotificacionService()

    def get_envio(self, guia: str) -> Envio:
        envio = self.envio_repo.get_by_guia(guia)
        if not envio:
            raise EntidadNoEncontradaException("Envío", guia)
        return envio

    def registrar_envio(self, dto: EnvioCreateDTO) -> EnvioResponseDTO:
        if self.envio_repo.existe(dto.guia.strip().upper()):
            raise GuiaDuplicadaException(dto.guia.strip().upper())
        dir_orig = Direccion(
            calle=dto.direccion_origen.calle,
            numero=dto.direccion_origen.numero,
            colonia=dto.direccion_origen.colonia,
            ciudad=dto.direccion_origen.ciudad,
            codigo_postal=dto.direccion_origen.codigo_postal,
        )
        dir_dest = Direccion(
            calle=dto.direccion_destino.calle,
            numero=dto.direccion_destino.numero,
            colonia=dto.direccion_destino.colonia,
            ciudad=dto.direccion_destino.ciudad,
            codigo_postal=dto.direccion_destino.codigo_postal,
        )
        dim = Dimensiones(
            largo_cm=dto.largo_cm,
            ancho_cm=dto.ancho_cm,
            alto_cm=dto.alto_cm,
        )
        paq = Paquete(
            peso_kg=dto.peso_kg,
            dimensiones=dim,
            descripcion=dto.descripcion_paquete,
        )
        seg = Seguro(
            amparado=dto.seguro_amparado,
            valor_declarado=dto.valor_declarado,
        )

        envio = Envio.crear_nuevo(
            guia_codigo=dto.guia,
            remitente_id=dto.remitente_id,
            destinatario_nombre=dto.destinatario_nombre,
            direccion_origen=dir_orig,
            direccion_destino=dir_dest,
            paquete=paq,
            seguro=seg,
            flete_monto=dto.flete_monto,
        )

        # Sugerir CEDIS de entrada
        try:
            cedis = self.cedis_service.sugerir_cedis(dir_dest.codigo_postal)
            envio.cedis_actual = cedis
        except Exception:
            envio.cedis_actual = "CEDIS-REGIONAL-DEFAULT"

        self.envio_repo.save(envio)
        self.envio_repo.commit()
        return self._to_response_dto(envio)

    def cancelar_envio(self, guia: str, motivo: str) -> EnvioResponseDTO:
        """Regla 1 (US2): Cancelación exclusiva en sucursal."""
        envio = self.get_envio(guia)
        try:
            envio.cancelar(motivo)
            self.envio_repo.save(envio)
            self.envio_repo.commit()
            return self._to_response_dto(envio)
        except Exception:
            self.envio_repo.rollback()
            raise

    def actualizar_direccion_destino(
        self,
        guia: str,
        nueva_dir_dto: Direccion,
        rol_solicitante: RolUsuario,
    ) -> EnvioResponseDTO:
        """Regla 3 (US7): Cambio de dirección antes de arribo a CEDIS destino."""
        envio = self.get_envio(guia)
        try:
            envio.actualizar_direccion(nueva_dir_dto, rol_solicitante)
            self.envio_repo.save(envio)
            self.envio_repo.commit()
            return self._to_response_dto(envio)
        except Exception:
            self.envio_repo.rollback()
            raise

    def registrar_intento_fallido(self, guia: str, motivo: str) -> EnvioResponseDTO:
        """Regla 2 (US10): Manejo de intentos y devolución a origen tras 2 fallos."""
        envio = self.get_envio(guia)
        try:
            envio.registrar_intento_fallido(motivo)
            self.envio_repo.save(envio)
            self.envio_repo.commit()
            return self._to_response_dto(envio)
        except Exception:
            self.envio_repo.rollback()
            raise

    def dictaminar_indemnizacion(
        self,
        guia: str,
        monto_reclamado: Decimal,
        rol_dictaminador: RolUsuario,
    ) -> DictamenIndemnizacionResponseDTO:
        """Regla 4 (US4/US12): Cálculo e indemnización con póliza o flete."""
        envio = self.get_envio(guia)
        monto_aut = envio.dictaminar_indemnizacion(monto_reclamado, rol_dictaminador)
        return DictamenIndemnizacionResponseDTO(
            guia=guia,
            monto_reclamado=monto_reclamado,
            monto_autorizado=monto_aut.monto,
            tiene_seguro=envio.seguro.amparado,
            dictaminado_por=rol_dictaminador.value,
            mensaje=f"Indemnización aprobada por {monto_aut}. "
                    f"({'Valor declarado con seguro' if envio.seguro.amparado else 'Tope al costo del flete sin póliza'}).",
        )

    def _guardar(self, envio: Envio) -> None:
        """Persiste el agregado dentro de una transacción (Unit of Work); revierte si falla."""
        try:
            self.envio_repo.save(envio)
            self.envio_repo.commit()
        except Exception:
            self.envio_repo.rollback()
            raise

    def avanzar_envio(self, guia: str, destino: str, cedis_id: Optional[str] = None) -> EnvioResponseDTO:
        """Avanza el envío por la ruta logística (RECIBIDO -> ... -> EN_REPARTO)."""
        envio = self.get_envio(guia)
        try:
            estado_destino = EstadoEnvio(destino.strip().upper())
        except ValueError:
            raise DomainException(f"Estado destino desconocido: '{destino}'.", codigo="ESTADO_DESCONOCIDO")
        envio.avanzar(estado_destino, cedis_id)
        self._guardar(envio)
        return self._to_response_dto(envio)

    def entregar_envio(self, guia: str, receptor: str, evidencia_id: str) -> EnvioResponseDTO:
        """Regla 5 (US13): entrega final con nombre del receptor y evidencia."""
        envio = self.get_envio(guia)
        envio.entregar(receptor, evidencia_id)
        self._guardar(envio)
        return self._to_response_dto(envio)

    def reportar_incidencia(
        self, guia: str, tipo: str, descripcion: str, evidencia_id: str = ""
    ) -> IncidenciaResponseDTO:
        """Regla 6 (US9/US11): incidencias operativas; los daños notifican a Calidad y Seguros."""
        envio = self.get_envio(guia)
        try:
            tipo_enum = TipoIncidencia(tipo.strip().upper())
        except ValueError:
            raise DomainException(f"Tipo de incidencia desconocido: '{tipo}'.", codigo="TIPO_DESCONOCIDO")
        if tipo_enum == TipoIncidencia.DESTINATARIO_AUSENTE:
            raise DomainException(
                "Las ausencias se registran con el endpoint de intento fallido (regla de 2 intentos).",
                codigo="USAR_INTENTO_FALLIDO",
            )
        incidencia = envio.reportar_incidencia(tipo_enum, descripcion, evidencia_id)
        self._guardar(envio)
        if tipo_enum == TipoIncidencia.PAQUETE_DANADO:
            self.notificacion_service.enviar_alerta_rastreo(
                guia, f"Paquete dañado reportado. Evidencia: {incidencia.evidencia_id}", "CALIDAD_Y_SEGUROS"
            )
        return IncidenciaResponseDTO(
            incidencia_id=incidencia.incidencia_id,
            guia=guia,
            tipo=incidencia.tipo.value,
            descripcion=incidencia.descripcion,
            evidencia_id=incidencia.evidencia_id,
            estado_envio=envio.estado.value,
        )

    def obtener_rastreo(self, guia: str) -> RastreoResponseDTO:
        """US5: estado actual, historial de movimientos y fecha estimada de entrega."""
        envio = self.get_envio(guia)
        return RastreoResponseDTO(
            guia=envio.guia.codigo,
            estado_actual=envio.estado.value,
            cedis_actual=envio.cedis_actual,
            intentos_entrega=envio.intentos_entrega,
            fecha_estimada_entrega=envio.fecha_estimada_entrega(),
            historial=[
                MovimientoDTO(estado=m.estado.value, detalle=m.detalle, fecha=m.fecha)
                for m in envio.historial
            ],
        )

    def alertas_rastreo_detenido(self, ahora: Optional[datetime] = None) -> List[AlertaRastreoDTO]:
        """US6: envíos EN_TRANSITO con más de 24 h sin movimiento; notifica a Atención a Clientes."""
        ahora = ahora or datetime.now(timezone.utc)
        alertas: List[AlertaRastreoDTO] = []
        for envio in self.envio_repo.list_all():
            if envio.emitir_alerta_si_detenido(ahora):
                horas = round((ahora - envio.ultimo_movimiento).total_seconds() / 3600, 1)
                self.notificacion_service.enviar_alerta_rastreo(
                    envio.guia.codigo,
                    f"AlertaRastreoDetenido: {horas} h sin movimiento",
                    "ATENCION_CLIENTES",
                )
                alertas.append(
                    AlertaRastreoDTO(
                        guia=envio.guia.codigo,
                        estado=envio.estado.value,
                        horas_sin_movimiento=horas,
                    )
                )
        return alertas

    def _to_response_dto(self, envio: Envio) -> EnvioResponseDTO:
        return EnvioResponseDTO(
            guia=envio.guia.codigo,
            remitente_id=envio.remitente_id,
            destinatario_nombre=envio.destinatario_nombre,
            estado=envio.estado.value,
            intentos_entrega=envio.intentos_entrega,
            cedis_actual=envio.cedis_actual,
            flete_mxn=envio.flete.monto,
            seguro_amparado=envio.seguro.amparado,
            valor_declarado_mxn=envio.seguro.valor_declarado,
            origen_resumen=envio.direccion_origen.resumen(),
            destino_resumen=envio.direccion_destino.resumen(),
        )



class ReporteAppService:
    """Casos de uso de lectura analítica (US14 y US15). Separado del servicio transaccional (SRP)."""

    def __init__(self, envio_repo: SqlEnvioRepository):
        self.envio_repo = envio_repo

    def entregas_a_tiempo(self) -> ReporteEntregasATiempoDTO:
        """US14: porcentaje de envíos entregados dentro de la promesa de servicio."""
        entregados = [e for e in self.envio_repo.list_all() if e.estado == EstadoEnvio.ENTREGADO]
        a_tiempo = sum(1 for e in entregados if e.entregado_a_tiempo())
        porcentaje = round(a_tiempo * 100 / len(entregados), 2) if entregados else 0.0
        return ReporteEntregasATiempoDTO(
            total_entregados=len(entregados),
            entregados_a_tiempo=a_tiempo,
            porcentaje_a_tiempo=porcentaje,
            sla_horas=SLA_ENTREGA_HORAS,
        )

    def incidencias_por_tipo(self) -> ReporteIncidenciasDTO:
        """US15: conteo de incidencias agrupadas por tipo."""
        por_tipo = self.envio_repo.contar_incidencias_por_tipo()
        return ReporteIncidenciasDTO(total_incidencias=sum(por_tipo.values()), por_tipo=por_tipo)

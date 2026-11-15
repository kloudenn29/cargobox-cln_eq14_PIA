"""Entidades y Agregados del Dominio de CargoBox (Clean Architecture / DDD)."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from src.domain.enums import EstadoEnvio, EstadoOperacion, RolUsuario, TipoIncidencia
from src.domain.events import (
    AlertaRastreoDetenido,
    DireccionActualizada,
    EnvioCancelado,
    EnvioClasificado,
    EnvioEnTransito,
    EnvioEntregado,
    EnvioRegistrado,
    EventDispatcher,
    IncidenciaRegistrada,
    IndemnizacionDictaminada,
)
from src.domain.exceptions import (
    AutorizacionRequeridaException,
    DomainException,
    IntentoEntregaAgotadoException,
    ModificacionDireccionNoPermitidaException,
    TransicionInvalidaException,
)
from src.domain.state_machine import EnvioStateMachine, OperacionStateMachine
from src.domain.value_objects import Dimensiones, Dinero, Direccion, GuiaRastreo, Seguro


@dataclass
class Actor:
    """Entidad que representa a un Remitente / Cliente del sistema CargoBox."""
    actor_id: str
    nombre: str
    es_preferente: bool = False
    activo: bool = True
    ciudad: str = "Monterrey"

    def __post_init__(self):
        if not self.actor_id.strip():
            raise DomainException("El ID del actor no puede estar vacío.")
        self.es_preferente = bool(int(self.es_preferente)) if str(self.es_preferente).isdigit() else bool(self.es_preferente)
        self.activo = bool(int(self.activo)) if str(self.activo).isdigit() else bool(self.activo)


@dataclass
class Recurso:
    """Entidad del catálogo de servicios o tipos de paquete."""
    recurso_id: str
    descripcion: str
    precio_mxn: Decimal
    capacidad_o_stock: int
    habilitado: bool = True

    def __post_init__(self):
        if not self.recurso_id.strip():
            raise DomainException("El ID del recurso no puede estar vacío.")
        self.precio_mxn = Decimal(str(self.precio_mxn))
        self.capacidad_o_stock = int(self.capacidad_o_stock)
        self.habilitado = bool(int(self.habilitado)) if str(self.habilitado).isdigit() else bool(self.habilitado)


@dataclass
class DetalleOperacion:
    """Línea de detalle perteneciente a una operación comercial."""
    operacion_id: str
    recurso_id: str
    cantidad: int
    precio_unitario: Decimal = Decimal("0.00")
    recurso: Optional[Recurso] = None

    def __post_init__(self):
        self.cantidad = int(self.cantidad)
        if self.cantidad <= 0:
            raise DomainException("La cantidad debe ser mayor a 0.")
        self.precio_unitario = Decimal(str(self.precio_unitario))

    @property
    def subtotal(self) -> Decimal:
        return (self.precio_unitario * Decimal(self.cantidad)).quantize(Decimal("0.01"))


@dataclass
class Operacion:
    """Agregado Raíz para las transacciones operativas del dataset."""
    operacion_id: str
    actor_id: str
    estado: EstadoOperacion = EstadoOperacion.RECIBIDO
    fecha_solicitud: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    promocion_activa: bool = False
    autorizado: bool = True
    referencia: str = ""
    actor: Optional[Actor] = None
    detalles: List[DetalleOperacion] = field(default_factory=list)

    def __post_init__(self):
        if isinstance(self.estado, str):
            self.estado = EstadoOperacion(self.estado)
        self.promocion_activa = bool(int(self.promocion_activa)) if str(self.promocion_activa).isdigit() else bool(self.promocion_activa)
        self.autorizado = bool(int(self.autorizado)) if str(self.autorizado).isdigit() else bool(self.autorizado)

    def calcular_total(self) -> Decimal:
        """Calcula el total sumando (precio_unitario * cantidad) de cada línea usando Decimal."""
        total = Decimal("0.00")
        for d in self.detalles:
            total += d.subtotal
        return total.quantize(Decimal("0.01"))

    @property
    def total_calculado(self) -> Decimal:
        return self.calcular_total()

    def transicionar(self, accion: str) -> EstadoOperacion:
        """Aplica la máquina de estados sobre la operación."""
        nuevo_estado = OperacionStateMachine.ejecutar_transicion(
            operacion_id=self.operacion_id,
            estado_actual=self.estado,
            accion=accion
        )
        self.estado = nuevo_estado
        return nuevo_estado


@dataclass
class Paquete:
    """Entidad que describe las características físicas de la carga."""
    peso_kg: Decimal
    dimensiones: Dimensiones
    descripcion: str = "Paquete general"
    contenido_fragil: bool = False

    def __post_init__(self):
        self.peso_kg = Decimal(str(self.peso_kg))
        if self.peso_kg <= Decimal("0.00"):
            raise DomainException("El peso real del paquete debe ser mayor a 0 kg.")
        if self.peso_kg > Decimal("70.00"):
            raise DomainException("El peso máximo por paquete para servicio express es de 70 kg.")

    @property
    def peso_facturable_kg(self) -> Decimal:
        """En paquetería se factura el mayor entre peso real y peso volumétrico."""
        return max(self.peso_kg, self.dimensiones.peso_volumetrico_kg)


@dataclass
class Incidencia:
    """Entidad que registra un evento anómalo durante el tránsito o entrega."""
    incidencia_id: str
    guia: str
    tipo: TipoIncidencia
    descripcion: str
    fecha_reporte: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resuelta: bool = False
    evidencia_id: str = ""


@dataclass
class MovimientoEnvio:
    """Entrada del historial de rastreo: cada cambio de estado queda registrado (US5)."""
    estado: EstadoEnvio
    detalle: str = ""
    fecha: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# Promesa de servicio (SLA): un envío se considera "a tiempo" si se entrega dentro de este plazo (US14).
SLA_ENTREGA_HORAS = 72
# Un envío EN_TRANSITO sin movimientos por más de este tiempo genera alerta (US6).
HORAS_RASTREO_DETENIDO = 24


@dataclass
class Envio:
    """Agregado Raíz principal del dominio CargoBox."""
    guia: GuiaRastreo
    remitente_id: str
    destinatario_nombre: str
    direccion_origen: Direccion
    direccion_destino: Direccion
    paquete: Paquete
    seguro: Seguro
    flete: Dinero
    estado: EstadoEnvio = EstadoEnvio.RECIBIDO
    intentos_entrega: int = 0
    cedis_actual: str = "CEDIS-ORIGEN-MTY"
    fecha_creacion: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    incidencias: List[Incidencia] = field(default_factory=list)
    historial: List[MovimientoEnvio] = field(default_factory=list)

    def __post_init__(self):
        if not self.destinatario_nombre.strip():
            raise DomainException("El nombre del destinatario es obligatorio.")
        if self.flete.monto <= Decimal("0.00"):
            raise DomainException("El costo de flete debe ser mayor a $0.00 MXN.")

    @classmethod
    def crear_nuevo(
        cls,
        guia_codigo: str,
        remitente_id: str,
        destinatario_nombre: str,
        direccion_origen: Direccion,
        direccion_destino: Direccion,
        paquete: Paquete,
        seguro: Seguro,
        flete_monto: Decimal,
    ) -> "Envio":
        envio = cls(
            guia=GuiaRastreo(guia_codigo),
            remitente_id=remitente_id,
            destinatario_nombre=destinatario_nombre,
            direccion_origen=direccion_origen,
            direccion_destino=direccion_destino,
            paquete=paquete,
            seguro=seguro,
            flete=Dinero(flete_monto),
            estado=EstadoEnvio.RECIBIDO,
        )
        envio.historial.append(
            MovimientoEnvio(EstadoEnvio.RECIBIDO, "Envío registrado en sucursal", envio.fecha_creacion)
        )
        EventDispatcher.dispatch(
            EnvioRegistrado(
                aggregate_id=guia_codigo,
                guia=guia_codigo,
                remitente_id=remitente_id,
                peso_kg=float(paquete.peso_kg),
            )
        )
        return envio

    # ------------------------------------------------------------------------
    # Historial de rastreo (US5) y consultas de tiempo (US6, US14)
    # ------------------------------------------------------------------------
    def _mover(self, nuevo_estado: EstadoEnvio, detalle: str) -> None:
        """Cambia el estado y deja constancia en el historial de rastreo."""
        self.estado = nuevo_estado
        self.historial.append(MovimientoEnvio(nuevo_estado, detalle))

    @property
    def ultimo_movimiento(self) -> datetime:
        return self.historial[-1].fecha if self.historial else self.fecha_creacion

    def esta_detenido(self, ahora: Optional[datetime] = None, horas: int = HORAS_RASTREO_DETENIDO) -> bool:
        """US6: EN_TRANSITO con más de `horas` sin registrar movimiento."""
        ahora = ahora or datetime.now(timezone.utc)
        return (
            self.estado == EstadoEnvio.EN_TRANSITO
            and ahora - self.ultimo_movimiento > timedelta(hours=horas)
        )

    def fecha_estimada_entrega(self) -> datetime:
        return self.fecha_creacion + timedelta(hours=SLA_ENTREGA_HORAS)

    def entregado_a_tiempo(self) -> bool:
        """US14: entregado dentro de la promesa de servicio."""
        return (
            self.estado == EstadoEnvio.ENTREGADO
            and self.ultimo_movimiento <= self.fecha_estimada_entrega()
        )

    def emitir_alerta_si_detenido(self, ahora: Optional[datetime] = None) -> bool:
        """US6: publica el evento AlertaRastreoDetenido si el envío lleva >24h sin movimiento."""
        ahora = ahora or datetime.now(timezone.utc)
        if not self.esta_detenido(ahora):
            return False
        horas = (ahora - self.ultimo_movimiento).total_seconds() / 3600
        EventDispatcher.dispatch(
            AlertaRastreoDetenido(aggregate_id=self.guia.codigo, horas_sin_movimiento=round(horas, 1))
        )
        return True

    # ------------------------------------------------------------------------
    # Avance por la red logística (RECIBIDO -> CLASIFICADO -> EN_TRANSITO -> ...)
    # ------------------------------------------------------------------------
    def avanzar(self, destino: EstadoEnvio, cedis_id: Optional[str] = None) -> EstadoEnvio:
        """Avanza el envío al siguiente estado válido; rechaza saltos y retrocesos."""
        estado_anterior = self.estado
        EnvioStateMachine.validar_avance(estado_anterior, destino)
        if cedis_id and cedis_id.strip():
            self.cedis_actual = cedis_id.strip()
        self._mover(destino, f"Cambio de estado {estado_anterior.value} -> {destino.value} en {self.cedis_actual}")
        if destino == EstadoEnvio.CLASIFICADO:
            EventDispatcher.dispatch(EnvioClasificado(aggregate_id=self.guia.codigo, cedis_id=self.cedis_actual))
        elif destino == EstadoEnvio.EN_TRANSITO:
            EventDispatcher.dispatch(
                EnvioEnTransito(
                    aggregate_id=self.guia.codigo,
                    cedis_origen="CEDIS-ORIGEN-MTY",
                    cedis_destino=self.cedis_actual,
                )
            )
        return self.estado

    # ------------------------------------------------------------------------
    # REGLA 1 (US2): Cancelación de Envío
    # ------------------------------------------------------------------------
    def cancelar(self, motivo: str) -> None:
        """Solo se permite cancelar si el envío se encuentra en sucursal (RECIBIDO)."""
        EnvioStateMachine.validar_cancelacion(self.estado)
        if not motivo.strip():
            raise DomainException("Debe indicarse un motivo válido de cancelación.")
        self._mover(EstadoEnvio.CANCELADO, f"Cancelado en sucursal: {motivo}")
        EventDispatcher.dispatch(
            EnvioCancelado(aggregate_id=self.guia.codigo, motivo=motivo)
        )

    # ------------------------------------------------------------------------
    # REGLA 2 (US10): Intentos de Entrega Fallidos
    # ------------------------------------------------------------------------
    def registrar_intento_fallido(self, motivo: str) -> EstadoEnvio:
        """Gestiona los intentos de entrega a domicilio."""
        if self.intentos_entrega >= EnvioStateMachine.MAX_INTENTOS:
            raise IntentoEntregaAgotadoException(self.intentos_entrega)
        if self.estado != EstadoEnvio.EN_REPARTO:
            raise TransicionInvalidaException(
                self.estado.value,
                "INTENTO_FALLIDO",
                "Solo puede registrarse un intento fallido cuando el envío está EN_REPARTO.",
            )
        nuevo_estado, nuevos_intentos = EnvioStateMachine.procesar_intento_fallido(
            guia=self.guia.codigo,
            intentos_actuales=self.intentos_entrega
        )
        self.intentos_entrega = nuevos_intentos
        self.incidencias.append(
            Incidencia(
                incidencia_id=f"INC-{self.guia.codigo}-{len(self.incidencias) + 1}",
                guia=self.guia.codigo,
                tipo=TipoIncidencia.DESTINATARIO_AUSENTE,
                descripcion=motivo,
            )
        )
        self._mover(nuevo_estado, f"Intento de entrega fallido #{nuevos_intentos}: {motivo}")
        return nuevo_estado

    # ------------------------------------------------------------------------
    # REGLA 3 (US7): Modificación de Dirección de Entrega
    # ------------------------------------------------------------------------
    def actualizar_direccion(self, nueva_direccion: Direccion, rol_solicitante: RolUsuario) -> None:
        """Solo permitida antes de arribar a distribución local en CEDIS destino."""
        roles_permitidos = {RolUsuario.REMITENTE, RolUsuario.ATENCION_CLIENTES, RolUsuario.ADMINISTRADOR}
        if rol_solicitante not in roles_permitidos:
            raise AutorizacionRequeridaException(f"El rol {rol_solicitante.value} no tiene autorización para modificar direcciones de entrega.")

        # Si ya arribó al CEDIS destino o está en reparto, se bloquea la modificación
        estados_bloqueados = {
            EstadoEnvio.DISTRIBUCION_LOCAL,
            EstadoEnvio.EN_REPARTO,
            EstadoEnvio.ENTREGADO,
            EstadoEnvio.CANCELADO,
            EstadoEnvio.DEVOLUCION_ORIGEN,
        }
        if self.estado in estados_bloqueados:
            raise ModificacionDireccionNoPermitidaException(self.estado.value)

        self.direccion_destino = nueva_direccion
        EventDispatcher.dispatch(
            DireccionActualizada(
                aggregate_id=self.guia.codigo,
                nueva_direccion=nueva_direccion.resumen(),
                autorizado_por=rol_solicitante.value,
            )
        )

    # ------------------------------------------------------------------------
    # REGLA 4 (US4/US12): Dictamen de Indemnizaciones
    # ------------------------------------------------------------------------
    def dictaminar_indemnizacion(self, monto_danio_reclamado: Decimal, rol_dictaminador: RolUsuario) -> Dinero:
        """
        Calcula el monto autorizado de indemnización:
        - Con seguro: cubre hasta el valor declarado.
        - Sin seguro: topado estrictamente al costo del flete ($350 MXN estándar).
        """
        roles_autorizados = {RolUsuario.ANALISTA_CALIDAD, RolUsuario.ADMINISTRADOR}
        if rol_dictaminador not in roles_autorizados:
            raise AutorizacionRequeridaException(f"El rol {rol_dictaminador.value} no tiene facultades para dictaminar indemnizaciones financieras.")

        reclamado = Decimal(str(monto_danio_reclamado))
        if reclamado <= Decimal("0.00"):
            raise DomainException("El monto reclamado debe ser mayor a $0.00 MXN.")

        if self.seguro.amparado:
            # Cobertura hasta el valor declarado
            monto_final = min(reclamado, self.seguro.valor_declarado)
        else:
            # Cobertura máxima limitada al flete
            monto_final = min(reclamado, self.flete.monto)

        monto_dictaminado = Dinero(monto_final)
        EventDispatcher.dispatch(
            IndemnizacionDictaminada(
                aggregate_id=self.guia.codigo,
                monto_autorizado=str(monto_dictaminado.monto),
                tiene_seguro=self.seguro.amparado,
                dictaminado_por=rol_dictaminador.value,
            )
        )
        return monto_dictaminado

    # ------------------------------------------------------------------------
    # REGLA 5 (US13): Entrega Exitosa con Evidencia
    # ------------------------------------------------------------------------
    def entregar(self, receptor: str, evidencia_id: str) -> None:
        """Registra la entrega final del paquete."""
        if self.estado != EstadoEnvio.EN_REPARTO:
            raise DomainException(f"Para entregar un paquete debe estar EN_REPARTO. Estado actual: {self.estado.value}.")
        if not receptor.strip() or not evidencia_id.strip():
            raise DomainException("La entrega requiere el nombre de quien recibe y el identificador de la evidencia física o digital.")
        self._mover(EstadoEnvio.ENTREGADO, f"Entregado a {receptor.strip()} (evidencia {evidencia_id.strip()})")
        EventDispatcher.dispatch(
            EnvioEntregado(
                aggregate_id=self.guia.codigo,
                receptor=receptor,
                evidencia_id=evidencia_id,
            )
        )

    # ------------------------------------------------------------------------
    # REGLA 6 (US9/US11): Incidencias operativas (dirección incorrecta, daño, etc.)
    # ------------------------------------------------------------------------
    def reportar_incidencia(
        self,
        tipo: TipoIncidencia,
        descripcion: str,
        evidencia_id: str = "",
    ) -> Incidencia:
        """
        - PAQUETE_DANADO exige evidencia (foto) para iniciar el peritaje (US11).
        - DIRECCION_INCORRECTA solo aplica EN_REPARTO y regresa el paquete a DISTRIBUCION_LOCAL (US9).
        """
        if self.estado in (EstadoEnvio.CANCELADO,):
            raise DomainException("No se pueden registrar incidencias en un envío cancelado.")
        if not descripcion.strip():
            raise DomainException("La incidencia requiere una descripción.")
        if tipo == TipoIncidencia.PAQUETE_DANADO and not evidencia_id.strip():
            raise DomainException("El registro de paquete dañado requiere evidencia fotográfica (evidencia_id).")
        if tipo == TipoIncidencia.DIRECCION_INCORRECTA and self.estado != EstadoEnvio.EN_REPARTO:
            raise TransicionInvalidaException(
                self.estado.value,
                tipo.value,
                "La dirección incorrecta solo se reporta con el paquete EN_REPARTO.",
            )

        incidencia = Incidencia(
            incidencia_id=f"INC-{self.guia.codigo}-{len(self.incidencias) + 1}",
            guia=self.guia.codigo,
            tipo=tipo,
            descripcion=descripcion.strip(),
            evidencia_id=evidencia_id.strip(),
        )
        self.incidencias.append(incidencia)
        if tipo == TipoIncidencia.DIRECCION_INCORRECTA:
            self._mover(EstadoEnvio.DISTRIBUCION_LOCAL, f"Dirección incorrecta: {descripcion.strip()}")
        EventDispatcher.dispatch(
            IncidenciaRegistrada(
                aggregate_id=self.guia.codigo,
                tipo=tipo.value,
                evidencia_id=incidencia.evidencia_id,
            )
        )
        return incidencia

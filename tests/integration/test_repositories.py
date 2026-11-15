"""Pruebas de integración para los Repositorios SQLAlchemy de CargoBox."""

from decimal import Decimal

from src.domain.entities import DetalleOperacion, Operacion
from src.domain.enums import EstadoEnvio, EstadoOperacion


class TestSqlActorRepository:
    def test_guardar_y_recuperar(self, actor_repo, actor_activo):
        actor_repo.save(actor_activo)
        actor_repo.session.commit()

        recuperado = actor_repo.get_by_id(actor_activo.actor_id)
        assert recuperado is not None
        assert recuperado.actor_id == actor_activo.actor_id
        assert recuperado.nombre == actor_activo.nombre
        assert recuperado.activo is True

    def test_actor_no_existente(self, actor_repo):
        assert actor_repo.get_by_id("NO-EXISTE") is None

    def test_listar_todos(self, actor_repo, actor_activo, actor_preferente):
        actor_repo.save(actor_activo)
        actor_repo.save(actor_preferente)
        actor_repo.session.commit()

        todos = actor_repo.list_all()
        assert len(todos) >= 2


class TestSqlCatalogoRepository:
    def test_guardar_y_recuperar(self, catalogo_repo, recurso_paquete):
        catalogo_repo.save(recurso_paquete)
        catalogo_repo.session.commit()

        recuperado = catalogo_repo.get_by_id(recurso_paquete.recurso_id)
        assert recuperado is not None
        assert recuperado.precio_mxn == Decimal("543.00")
        assert recuperado.capacidad_o_stock == 13


class TestSqlOperacionRepository:
    def test_guardar_operacion_con_detalles_y_commit(
        self, operacion_repo, actor_repo, catalogo_repo, actor_activo, recurso_paquete
    ):
        actor_repo.save(actor_activo)
        catalogo_repo.save(recurso_paquete)
        actor_repo.session.commit()

        detalle = DetalleOperacion(
            operacion_id="OP-INT-1",
            recurso_id=recurso_paquete.recurso_id,
            cantidad=3,
            precio_unitario=recurso_paquete.precio_mxn,
            recurso=recurso_paquete,
        )
        op = Operacion(
            operacion_id="OP-INT-1",
            actor_id=actor_activo.actor_id,
            estado=EstadoOperacion.RECIBIDO,
            actor=actor_activo,
            detalles=[detalle],
        )

        operacion_repo.save(op)
        operacion_repo.commit()

        recuperado = operacion_repo.get_by_id("OP-INT-1")
        assert recuperado is not None
        assert recuperado.actor_id == actor_activo.actor_id
        assert len(recuperado.detalles) == 1
        assert recuperado.detalles[0].cantidad == 3
        assert recuperado.calcular_total() == Decimal("1629.00")

    def test_rollback_aislamiento(self, operacion_repo, actor_repo, actor_activo):
        actor_repo.save(actor_activo)
        actor_repo.session.commit()

        op = Operacion(
            operacion_id="OP-ROLLBACK",
            actor_id=actor_activo.actor_id,
            estado=EstadoOperacion.RECIBIDO,
        )
        operacion_repo.save(op)
        operacion_repo.rollback()

        assert operacion_repo.get_by_id("OP-ROLLBACK") is None


class TestSqlEnvioRepository:
    def test_guardar_y_recuperar_envio(self, envio_repo, envio_basico):
        envio_repo.save(envio_basico)
        envio_repo.commit()

        recuperado = envio_repo.get_by_guia(envio_basico.guia.codigo)
        assert recuperado is not None
        assert recuperado.remitente_id == envio_basico.remitente_id
        assert recuperado.estado == EstadoEnvio.RECIBIDO
        assert recuperado.flete.monto == Decimal("350.00")
        assert recuperado.direccion_destino.ciudad == "Guadalajara"

    def test_rollback_envio(self, envio_repo, envio_basico):
        envio_repo.save(envio_basico)
        envio_repo.rollback()

        assert envio_repo.get_by_guia(envio_basico.guia.codigo) is None

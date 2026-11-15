"""Fixtures compartidos para las pruebas automatizadas de CargoBox."""

import os
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.main import app
from src.domain.entities import Actor, Envio, Paquete, Recurso
from src.domain.enums import EstadoEnvio
from src.domain.events import EventDispatcher
from src.domain.value_objects import Dimensiones, Dinero, Direccion, GuiaRastreo, Seguro
from src.infrastructure.database import Base, get_db
from src.infrastructure.repositories import (
    SqlActorRepository,
    SqlCatalogoRepository,
    SqlEnvioRepository,
    SqlOperacionRepository,
)


@pytest.fixture(autouse=True)
def clear_events():
    """Limpia el despachador de eventos antes de cada prueba."""
    EventDispatcher.clear()
    yield
    EventDispatcher.clear()


@pytest.fixture
def engine():
    """Motor SQLAlchemy en memoria para pruebas aisladas."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture
def session(engine):
    """Sesión de base de datos para pruebas."""
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()


@pytest.fixture
def actor_repo(session):
    return SqlActorRepository(session)


@pytest.fixture
def catalogo_repo(session):
    return SqlCatalogoRepository(session)


@pytest.fixture
def operacion_repo(session):
    return SqlOperacionRepository(session)


@pytest.fixture
def envio_repo(session):
    return SqlEnvioRepository(session)


# -----------------------------------------------------------------------
# Entidades de ejemplo
# -----------------------------------------------------------------------
@pytest.fixture
def actor_activo():
    return Actor(
        actor_id="CAR-C001",
        nombre="Remitente 01",
        es_preferente=False,
        activo=True,
        ciudad="Monterrey",
    )


@pytest.fixture
def actor_preferente():
    return Actor(
        actor_id="CAR-C002",
        nombre="Remitente VIP 02",
        es_preferente=True,
        activo=True,
        ciudad="Apodaca",
    )


@pytest.fixture
def actor_inactivo():
    return Actor(
        actor_id="CAR-C003",
        nombre="Remitente Suspendido 03",
        es_preferente=False,
        activo=False,
        ciudad="Monterrey",
    )


@pytest.fixture
def recurso_paquete():
    return Recurso(
        recurso_id="CAR-P001",
        descripcion="Paquete pequeño 01",
        precio_mxn=Decimal("543.00"),
        capacidad_o_stock=13,
        habilitado=True,
    )


@pytest.fixture
def recurso_caro():
    return Recurso(
        recurso_id="CAR-P002",
        descripcion="Paquete mediano 02",
        precio_mxn=Decimal("614.00"),
        capacidad_o_stock=16,
        habilitado=True,
    )


@pytest.fixture
def dir_origen():
    return Direccion(
        calle="Av. Universidad",
        numero="1500",
        colonia="Centro",
        ciudad="Monterrey",
        codigo_postal="64000",
    )


@pytest.fixture
def dir_destino():
    return Direccion(
        calle="Calle Hidalgo",
        numero="200",
        colonia="Zona Centro",
        ciudad="Guadalajara",
        codigo_postal="44100",
    )


@pytest.fixture
def dimensiones_estandar():
    return Dimensiones(largo_cm=30, ancho_cm=20, alto_cm=15)


@pytest.fixture
def paquete_normal(dimensiones_estandar):
    return Paquete(peso_kg=Decimal("5.0"), dimensiones=dimensiones_estandar)


@pytest.fixture
def seguro_con_poliza():
    return Seguro(amparado=True, valor_declarado=Decimal("5000.00"))


@pytest.fixture
def seguro_sin_poliza():
    return Seguro(amparado=False, valor_declarado=Decimal("0.00"))


@pytest.fixture
def envio_basico(dir_origen, dir_destino, paquete_normal, seguro_sin_poliza):
    """Envío básico en estado RECIBIDO sin seguro."""
    return Envio(
        guia=GuiaRastreo("CBX-001-TEST"),
        remitente_id="CAR-C001",
        destinatario_nombre="Juan Pérez",
        direccion_origen=dir_origen,
        direccion_destino=dir_destino,
        paquete=paquete_normal,
        seguro=seguro_sin_poliza,
        flete=Dinero(Decimal("350.00")),
        estado=EstadoEnvio.RECIBIDO,
    )


@pytest.fixture
def envio_asegurado(dir_origen, dir_destino, paquete_normal, seguro_con_poliza):
    """Envío con seguro contratado en estado RECIBIDO."""
    return Envio(
        guia=GuiaRastreo("CBX-002-SEGURO"),
        remitente_id="CAR-C002",
        destinatario_nombre="María López",
        direccion_origen=dir_origen,
        direccion_destino=dir_destino,
        paquete=paquete_normal,
        seguro=seguro_con_poliza,
        flete=Dinero(Decimal("500.00")),
        estado=EstadoEnvio.RECIBIDO,
    )


@pytest.fixture
def envio_en_transito(envio_basico):
    """Envío que ya está en tránsito."""
    envio_basico.estado = EstadoEnvio.EN_TRANSITO
    return envio_basico


@pytest.fixture
def envio_en_distribucion_local(envio_basico):
    """Envío que ya arribó al CEDIS destino."""
    envio_basico.estado = EstadoEnvio.DISTRIBUCION_LOCAL
    return envio_basico


@pytest.fixture
def envio_en_reparto(envio_basico):
    """Envío que recorrió la ruta completa y está EN_REPARTO (con historial real)."""
    for destino in (
        EstadoEnvio.CLASIFICADO,
        EstadoEnvio.EN_TRANSITO,
        EstadoEnvio.DISTRIBUCION_LOCAL,
        EstadoEnvio.EN_REPARTO,
    ):
        envio_basico.avanzar(destino)
    return envio_basico


@pytest.fixture
def datos_dir():
    """Ruta al directorio de datos CSV del dataset del PIA."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "datos",
    )


# -----------------------------------------------------------------------
# Cliente HTTP de pruebas (FastAPI TestClient con BD SQLite en memoria)
# -----------------------------------------------------------------------
@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

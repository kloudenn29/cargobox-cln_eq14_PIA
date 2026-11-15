"""Configuración de Base de Datos SQLAlchemy (PostgreSQL en producción, SQLite en local y pruebas)."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _normalizar_url(url: str) -> str:
    """Render/Railway entregan 'postgres://' o 'postgresql://'; se fija el driver psycopg2 explícitamente."""
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg2://" + url[len(prefijo):]
    return url


# 12-Factor: la configuración llega por variable de entorno (SQLite local por defecto).
DATABASE_URL = _normalizar_url(os.getenv("DATABASE_URL", "sqlite:///./cargobox.sqlite3"))

# connect_args={"check_same_thread": False} es necesario para SQLite en FastAPI multihilo
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Generador de sesiones de base de datos para inyección de dependencias."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(custom_engine=None):
    """Crea todas las tablas si no existen."""
    eng = custom_engine or engine
    Base.metadata.create_all(bind=eng)


"""Inyección de dependencias para los Routers de FastAPI."""

from fastapi import Depends
from sqlalchemy.orm import Session

from src.application.services import EnvioAppService, OperacionAppService, ReporteAppService
from src.infrastructure.database import get_db
from src.infrastructure.repositories import (
    SqlActorRepository,
    SqlCatalogoRepository,
    SqlEnvioRepository,
    SqlOperacionRepository,
)


def get_actor_repo(db: Session = Depends(get_db)) -> SqlActorRepository:
    return SqlActorRepository(db)


def get_catalogo_repo(db: Session = Depends(get_db)) -> SqlCatalogoRepository:
    return SqlCatalogoRepository(db)


def get_operacion_repo(db: Session = Depends(get_db)) -> SqlOperacionRepository:
    return SqlOperacionRepository(db)


def get_envio_repo(db: Session = Depends(get_db)) -> SqlEnvioRepository:
    return SqlEnvioRepository(db)


def get_operacion_service(
    op_repo: SqlOperacionRepository = Depends(get_operacion_repo),
    actor_repo: SqlActorRepository = Depends(get_actor_repo),
    cat_repo: SqlCatalogoRepository = Depends(get_catalogo_repo),
) -> OperacionAppService:
    return OperacionAppService(op_repo, actor_repo, cat_repo)


def get_envio_service(
    envio_repo: SqlEnvioRepository = Depends(get_envio_repo),
) -> EnvioAppService:
    return EnvioAppService(envio_repo)



def get_reporte_service(
    envio_repo: SqlEnvioRepository = Depends(get_envio_repo),
) -> ReporteAppService:
    return ReporteAppService(envio_repo)

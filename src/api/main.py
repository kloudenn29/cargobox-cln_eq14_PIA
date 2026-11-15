"""Aplicación FastAPI principal de CargoBox — API REST con documentación OpenAPI/Swagger."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers.envios import router as envios_router
from src.api.routers.operaciones import router as operaciones_router
from src.api.routers.reportes import router as reportes_router
from src.api.routers.salud import router as salud_router
from src.infrastructure.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Crea las tablas al iniciar la aplicación."""
    init_db()
    yield


app = FastAPI(
    title="CargoBox API — Lógica de Negocios",
    description=(
        "Sistema de gestión logística y paquetería express nacional.\n\n"
        "Implementa DDD, Specification Pattern, State Machine y Domain Events.\n\n"
        "**Equipo 14** — Componentes de Lógica de Negocios (CLN) AD2026"
    ),
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(salud_router)
app.include_router(operaciones_router)
app.include_router(envios_router)
app.include_router(reportes_router)

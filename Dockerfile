# ============================================================================
# CargoBox API — Equipo 14 (PIA CLN). Imagen única para app y pruebas.
# ============================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY src/ src/
COPY datos/ datos/
COPY scripts/ scripts/
COPY tests/ tests/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# 1) crea tablas y carga datos (idempotente)  2) levanta la API en $PORT (Render/Railway lo inyectan)
CMD ["sh", "-c", "python scripts/cargar_datos.py && uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT}"]

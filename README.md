# CargoBox — Producto Integrador de Aprendizaje (PIA)

![CI](https://github.com/kloudenn29/cargobox-cln_eq14_PIA/actions/workflows/ci.yml/badge.svg)

**Materia:** Componentes de Lógica de Negocios (CLN) — AD2026 · **Equipo:** 14 · **Profesor:** Miguel Ángel Gómez Marroquín

**Integrantes:**
- Pedro Omar Cardona Alvarez — 2226579
- Kloudenn Jafed Jiménez Valdivieso — 2226639
- Leonardo Acosta Morales — 2226717

| | |
|---|---|
| **Repositorio GitHub** | https://github.com/kloudenn29/cargobox-cln_eq14_PIA |
| **Sistema desplegado (Swagger UI)** | `PEGAR-AQUÍ-LA-URL-DE-RENDER/docs` |

---

## 1. ¿Qué es CargoBox?

API REST de paquetería express que implementa en código las reglas de negocio analizadas en las Unidades 2 y 3 (BRD, User Stories con Gherkin, BPMN y glosario). No tiene interfaz gráfica: la demostración se hace con **Swagger UI** (`/docs`).

Componentes del curso aplicados:
- **DDD:** agregados `Envio` y `Operacion`, entidades (`Incidencia`, `MovimientoEnvio`, `Paquete`…) y Value Objects (`Dinero`, `Direccion`, `Seguro`, `GuiaRastreo`…).
- **Specification:** `PuedeProcesarseSpecification` y `BeneficioReferenciaSpecification`, combinables con `&`, `|`, `~`.
- **State Machine:** `EnvioStateMachine` y `OperacionStateMachine` (sin saltos ni retrocesos).
- **Domain Events, Unit of Work, Repositorios y API REST documentada con OpenAPI.**

## 2. Estructura del repositorio

```text
cargobox-cln/
├── docs/
│   ├── BRD.md · USER_STORIES_GHERKIN.md · BPMN.md · GLOSARIO.md · MATRIZ_TRAZABILIDAD.md
│   ├── architecture/        # DDD_MODEL, UML_DIAGRAMS, PATRONES_Y_SOLID y 6 ADRs
│   └── api/                 # openapi.json y openapi_description.md
├── src/
│   ├── domain/              # entidades, value objects, specifications, state machine, eventos
│   ├── application/         # servicios (casos de uso) y DTOs
│   ├── infrastructure/      # SQLAlchemy (modelos, repositorios) y adaptadores externos (mocks)
│   └── api/                 # FastAPI: main, dependencias y routers
├── tests/                   # unit/ + integration/ + dataset/ (297 pruebas)
├── datos/                   # CSV oficiales y CSV resueltos (120 casos + 20 transiciones)
├── scripts/                 # cargar_datos.py, ejecutar_casos_alumno.py y demo.py
├── .github/workflows/ci.yml # CI/CD (lint, pruebas, dataset y Docker Compose)
├── docker-compose.yml       # db (PostgreSQL) + app + tests
├── Dockerfile · requirements.txt · pyproject.toml
└── .env.example             # variables de entorno sin secretos
```

## 3. Ejecución local (Windows PowerShell, SQLite)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # si falla: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt
python scripts/cargar_datos.py        # crea las tablas y carga los CSV
python -m uvicorn src.api.main:app --port 8000
```
Swagger UI: http://localhost:8000/docs · Health: http://localhost:8000/health

En Linux/macOS: `source .venv/bin/activate` en lugar de `Activate.ps1`.

## 4. Ejecución con Docker Compose (PostgreSQL)

```bash
cp .env.example .env        # opcional: cada variable tiene valor por defecto
docker compose up --build
```
Levanta `db` (PostgreSQL), `app` y `tests` (ruff + pytest con cobertura ≥ 80 %, termina al acabar).
Swagger UI: http://localhost:8080/docs

Para apagar y borrar los datos: `docker compose down -v`.

## 5. Pruebas y calidad

```bash
ruff check src tests
pytest                                    # 297 pruebas, cobertura ≈ 95 % (mínimo exigido 80 %)
python scripts/ejecutar_casos_alumno.py   # regenera los CSV resueltos del dataset oficial
python scripts/demo.py                    # recorrido de la API sin levantar el servidor
```

## 6. Variables de entorno (12-Factor)

| Variable | Uso |
|---|---|
| `DATABASE_URL` | Cadena de conexión (SQLite local o PostgreSQL). Acepta `postgres://` de Render/Railway. |
| `PORT` | Puerto interno de la API (la plataforma de despliegue lo inyecta). |
| `APP_PORT` | Puerto publicado en tu máquina con Docker Compose (por defecto 8080). |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Credenciales del servicio `db` en Docker Compose. |

## 7. Endpoints principales

| Método y ruta | Historia / regla |
|---|---|
| `POST /envios/` | US1, US3 (guía única), US8 (CEDIS) |
| `GET /envios/{guia}` · `GET /envios/{guia}/rastreo` | US5 |
| `POST /envios/{guia}/avanzar` | RN-07 avance secuencial |
| `POST /envios/{guia}/cancelar` | US2 / RN-01 |
| `POST /envios/{guia}/direccion` | US7 / RN-03 |
| `POST /envios/{guia}/intento-fallido` | US10 / RN-02 |
| `POST /envios/{guia}/incidencias` | US9, US11 / RN-09 |
| `POST /envios/{guia}/indemnizacion` | US4, US12 / RN-04 |
| `POST /envios/{guia}/entregar` | US13 / RN-07 |
| `GET /envios/alertas/rastreo-detenido` | US6 / RN-08 |
| `GET /reportes/entregas-a-tiempo` · `GET /reportes/incidencias` | US14, US15 |
| `/operaciones/...` | RN-05, RN-06 y transiciones del dataset |

La trazabilidad completa (BRD → US → regla → código → prueba) está en `docs/MATRIZ_TRAZABILIDAD.md`.

## 8. Guion de demostración en vivo (Swagger UI)

1. `POST /envios/` con una guía nueva (p. ej. `CBX-DEMO-001`) → `RECIBIDO` y CEDIS asignado por código postal. Repetir el mismo POST → **409** (guía única).
2. `POST /envios/CBX-DEMO-001/avanzar` con `EN_REPARTO` → **409** (no se permiten saltos).
3. `POST /envios/{guia}/cancelar` en un envío `RECIBIDO` → 200; en uno `EN_TRANSITO` → **409** (RN-01).
4. Avanzar `CLASIFICADO` → `EN_TRANSITO` → `DISTRIBUCION_LOCAL` → `EN_REPARTO`.
5. `POST .../incidencias` con `PAQUETE_DANADO` sin evidencia → **422**; con `FOTO_ROTURA_01` → 201.
6. `POST .../intento-fallido` dos veces (volviendo a `EN_REPARTO` entre ambos) → `DEVOLUCION_ORIGEN`; un tercero → **409**.
7. En otro envío `EN_REPARTO`: `POST .../entregar` → `ENTREGADO`; ver `GET .../rastreo` (historial completo).
8. `GET /reportes/entregas-a-tiempo` y `GET /reportes/incidencias`.

## 9. Despliegue (Render)

La misma imagen Docker se despliega como *Web Service* con una base PostgreSQL de Render; `DATABASE_URL` se configura como variable de entorno. Swagger queda activo en `https://<servicio>.onrender.com/docs`.

## 10. Guía de respuestas técnicas para la defensa

- **¿Cómo aplicaron DDD?** `Envio` es el agregado raíz: protege sus invariantes (cancelación solo en `RECIBIDO`, máximo 2 intentos, avance sin saltos, entrega solo con evidencia) y nadie cambia su estado sin pasar por sus métodos.
- **¿Por qué Specification?** Separa las reglas de validación de las entidades y permite combinarlas con `&`, `|`, `~`; se usa en `PuedeProcesarse` y `BeneficioReferencia`.
- **¿Cómo evita estados inválidos la State Machine?** Define el único camino válido por estado; cualquier salto lanza `TransicionInvalidaException` y la API responde 409.
- **¿Para qué sirven los mocks?** `MockCentroDistribucionService` simula el servicio externo de CEDIS, incluida su caída (el registro continúa con un CEDIS por defecto); `MockNotificacionService` simula las alertas a Calidad y a Atención a Clientes.
- **¿Cómo garantizan la persistencia correcta?** Unit of Work con `commit()`/`rollback()` en los servicios; pruebas de repositorio sobre SQLite en memoria y ejecución real sobre PostgreSQL con Docker Compose.
- **¿Cómo se ve la trazabilidad?** Cada US aparece en la matriz con su regla, su código y sus pruebas.

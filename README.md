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
| **Sistema desplegado (Swagger UI)** | https://cargobox-api-u98o.onrender.com/docs |
| **Interfaz web desplegada** | https://cargobox-api-u98o.onrender.com/ |

---
## 1. Estructura del repositorio

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
│   └── api/                 # FastAPI: main, dependencias, routers e interfaz web (static/index.html)
├── tests/                   # unit/ + integration/ + dataset/ (299 pruebas)
├── datos/                   # CSV oficiales y CSV resueltos (120 casos + 20 transiciones)
├── scripts/                 # cargar_datos.py, ejecutar_casos_alumno.py y demo.py
├── .github/workflows/ci.yml # CI/CD (lint, pruebas, dataset y Docker Compose)
├── docker-compose.yml       # db (PostgreSQL) + app + tests
├── Dockerfile · requirements.txt · pyproject.toml
└── .env.example             # variables de entorno sin secretos
```
## 2. Endpoints principales

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

## 3. Guion de demostración en vivo (Swagger UI)

1. `POST /envios/` con una guía nueva (p. ej. `CBX-DEMO-001`) → `RECIBIDO` y CEDIS asignado por código postal. Repetir el mismo POST → **409** (guía única).
2. `POST /envios/CBX-DEMO-001/avanzar` con `EN_REPARTO` → **409** (no se permiten saltos).
3. `POST /envios/{guia}/cancelar` en un envío `RECIBIDO` → 200; en uno `EN_TRANSITO` → **409** (RN-01).
4. Avanzar `CLASIFICADO` → `EN_TRANSITO` → `DISTRIBUCION_LOCAL` → `EN_REPARTO`.
5. `POST .../incidencias` con `PAQUETE_DANADO` sin evidencia → **422**; con `FOTO_ROTURA_01` → 201.
6. `POST .../intento-fallido` dos veces (volviendo a `EN_REPARTO` entre ambos) → `DEVOLUCION_ORIGEN`; un tercero → **409**.
7. En otro envío `EN_REPARTO`: `POST .../entregar` → `ENTREGADO`; ver `GET .../rastreo` (historial completo).
8. `GET /reportes/entregas-a-tiempo` y `GET /reportes/incidencias`.

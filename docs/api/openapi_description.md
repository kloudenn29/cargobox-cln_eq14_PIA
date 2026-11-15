# Documentación de Contratos y Endpoints de la API REST — CargoBox
**Especificación:** OpenAPI 3.1.0  
**Ruta Swagger UI:** `http://localhost:8000/docs`  
**Ruta ReDoc:** `http://localhost:8000/redoc`  
**Ruta JSON:** `http://localhost:8000/openapi.json`  

---

## 1. Endpoints de Salud y Monitoreo

### `GET /health`
* **Descripción:** Comprueba la disponibilidad del servicio y la conexión a la base de datos.
* **Respuesta Exitosa (200 OK):**
```json
{
  "status": "UP",
  "service": "CargoBox API",
  "version": "1.1.0",
  "timestamp": "2026-11-05T17:00:00Z",
  "database": "connected"
}
```

---

## 2. Endpoints de Operaciones Comerciales

### `POST /operaciones/`
* **Descripción:** Registra una nueva operación comercial en estado `RECIBIDO` y calcula el total con `Decimal`.
* **Código de Respuesta:** `201 Created` / `404 Not Found` (si el actor no existe) / `422 Unprocessable Entity`.

### `GET /operaciones/{operacion_id}`
* **Descripción:** Obtiene los datos consolidados y total de una operación.
* **Código de Respuesta:** `200 OK` / `404 Not Found`.

### `GET /operaciones/{operacion_id}/validar`
* **Descripción:** Ejecuta la especificación `PuedeProcesarseSpecification` (`cliente activo AND detalle no vacío AND autorización`).
* **Respuesta Exitosa (200 OK):**
```json
{
  "operacion_id": "CAR-O001",
  "regla": "puede_procesarse (cliente activo AND detalle no vacío AND autorización)",
  "cumple": true,
  "explicacion": "CUMPLE: (Cliente activo AND Detalle con 2 líneas) AND Operación autorizada"
}
```

### `GET /operaciones/{operacion_id}/beneficio`
* **Descripción:** Ejecuta la especificación `BeneficioReferenciaSpecification` (`VIP AND total >= 1500 AND NOT promoción`).
* **Respuesta Exitosa (200 OK):**
```json
{
  "operacion_id": "CAR-O001",
  "regla": "beneficio_referencia (VIP AND total >= 1500 MXN AND NOT promoción)",
  "cumple": false,
  "explicacion": "NO CUMPLE: [Izquierda: Cliente estándar (no preferente)]"
}
```

### `POST /operaciones/{operacion_id}/transicion`
* **Descripción:** Aplica una acción en la máquina de estados (`aprobar`, `completar`, `cancelar`).
* **Código de Respuesta:** `200 OK` / `409 Conflict` (si se intenta `saltar_estado` o `repetir_aprobacion`).

---

## 3. Endpoints de Envíos y Logística

### `POST /envios/`
* **Descripción:** Registra un nuevo envío, calcula peso volumétrico y asigna CEDIS por código postal.
* **Código de Respuesta:** `201 Created` / `409 Conflict` (guía duplicada) / `422 Unprocessable Entity`.

### `GET /envios/{guia}`
* **Descripción:** Consulta el estatus en tiempo real, ubicación de CEDIS e intentos de entrega.
* **Código de Respuesta:** `200 OK` / `404 Not Found`.

### `POST /envios/{guia}/cancelar`
* **Descripción:** Cancela el envío. Permitido exclusivamente en estado `RECIBIDO` (RN-01).
* **Código de Respuesta:** `200 OK` / `409 Conflict` (si el paquete ya salió a `EN_TRANSITO`).

### `POST /envios/{guia}/direccion`
* **Descripción:** Actualiza el domicilio de entrega antes de arribar a CEDIS destino (RN-03).
* **Código de Respuesta:** `200 OK` / `409 Conflict` (si ya está en distribución local).

### `POST /envios/{guia}/intento-fallido`
* **Descripción:** Registra visita fallida por cliente ausente. Solo válido con el envío `EN_REPARTO`. Al segundo intento detona `DEVOLUCION_ORIGEN` (RN-02).
* **Código de Respuesta:** `200 OK` / `409 Conflict` (si se supera el límite de 2 intentos o el envío no está `EN_REPARTO`).

### `POST /envios/{guia}/indemnizacion`
* **Descripción:** Dictamina compensación económica con o sin póliza de seguro (RN-04).
* **Código de Respuesta:** `200 OK` / `422 Unprocessable Entity`.


### `GET /envios/{guia}/rastreo` (US5)
* **Descripción:** Estado actual, historial de movimientos y fecha estimada de entrega (72 h).
* **Código de Respuesta:** `200 OK` / `404 Not Found`.

### `POST /envios/{guia}/avanzar` (RN-07)
* **Cuerpo:** `{"destino": "CLASIFICADO", "cedis_id": "CEDIS-OCCIDENTE-GUADALAJARA"}` (`cedis_id` es opcional).
* **Descripción:** Avanza al siguiente estado de la ruta: `CLASIFICADO → EN_TRANSITO → DISTRIBUCION_LOCAL → EN_REPARTO`.
* **Código de Respuesta:** `200 OK` / `404 Not Found` / `409 Conflict` (salto o retroceso de estado) / `422 Unprocessable Entity` (estado desconocido).

### `POST /envios/{guia}/entregar` (US13)
* **Cuerpo:** `{"receptor": "Laura Méndez", "evidencia_id": "FIRMA_DIGITAL_09"}`
* **Descripción:** Marca el envío como `ENTREGADO`; solo válido si está `EN_REPARTO` y con evidencia.
* **Código de Respuesta:** `200 OK` / `404 Not Found` / `409 Conflict`.

### `POST /envios/{guia}/incidencias` (US9, US11)
* **Cuerpo:** `{"tipo": "PAQUETE_DANADO", "descripcion": "Rotura en maniobras", "evidencia_id": "FOTO_ROTURA_01"}`
* **Tipos permitidos:** `DIRECCION_INCORRECTA`, `PAQUETE_DANADO`, `EXTRAVIO`, `RECHAZO` (la ausencia se registra con `/intento-fallido`).
* **Descripción:** El daño exige evidencia; la dirección incorrecta solo aplica `EN_REPARTO` y regresa el paquete a `DISTRIBUCION_LOCAL`.
* **Código de Respuesta:** `201 Created` / `404 Not Found` / `409 Conflict` / `422 Unprocessable Entity`.

### `GET /envios/alertas/rastreo-detenido` (US6)
* **Descripción:** Lista los envíos `EN_TRANSITO` con más de 24 h sin movimiento y notifica a Atención a Clientes.
* **Código de Respuesta:** `200 OK`.

---

## 4. Reportes Analíticos

### `GET /reportes/entregas-a-tiempo` (US14)
* **Respuesta Exitosa (200 OK):**
```json
{ "total_entregados": 2, "entregados_a_tiempo": 2, "porcentaje_a_tiempo": 100.0, "sla_horas": 72 }
```

### `GET /reportes/incidencias` (US15)
* **Respuesta Exitosa (200 OK):**
```json
{ "total_incidencias": 2, "por_tipo": { "PAQUETE_DANADO": 1, "DESTINATARIO_AUSENTE": 1 } }
```

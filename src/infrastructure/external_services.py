"""Servicios Externos y Adaptadores Simulados (Mocks) para Integraciones de CargoBox."""

from typing import Dict, Protocol


class ICentroDistribucionService(Protocol):
    """Protocolo / Puerto para el servicio de enrutamiento y asignación de CEDIS."""
    def sugerir_cedis(self, codigo_postal: str) -> str:
        """Determina el centro de distribución correspondiente al CP de destino."""
        ...


class MockCentroDistribucionService:
    """Adaptador simulado para asignación de centros de distribución regionales."""

    CEDIS_POR_CP: Dict[str, str] = {
        "64000": "CEDIS-NORTE-MONTERREY",
        "66600": "CEDIS-AEROPUERTO-APODACA",
        "01000": "CEDIS-CENTRO-CDMX",
        "44100": "CEDIS-OCCIDENTE-GUADALAJARA",
        "72000": "CEDIS-SUR-PUEBLA",
    }

    def __init__(self, simular_falla_red: bool = False):
        self.simular_falla_red = simular_falla_red

    def sugerir_cedis(self, codigo_postal: str) -> str:
        if self.simular_falla_red:
            raise ConnectionError("Falla de conectividad con el servicio central de enrutamiento CEDIS.")

        prefijo_2 = codigo_postal[:2] if len(codigo_postal) >= 2 else "00"
        if codigo_postal in self.CEDIS_POR_CP:
            return self.CEDIS_POR_CP[codigo_postal]
        elif prefijo_2 in ["64", "66", "67"]:
            return "CEDIS-REGIONAL-NORESTE"
        elif prefijo_2 in ["01", "02", "03", "04", "05"]:
            return "CEDIS-METROPOLITANO-CENTRO"
        elif prefijo_2 in ["44", "45"]:
            return "CEDIS-OCCIDENTE-JALISCO"
        return "CEDIS-HUB-NACIONAL-MTY"


class INotificacionService(Protocol):
    """Protocolo para envío de notificaciones y alertas de rastreo."""
    def enviar_alerta_rastreo(self, guia: str, mensaje: str, destinatario_contacto: str) -> bool:
        ...


class MockNotificacionService:
    """Adaptador simulado para despacho de alertas por SMS/Email."""

    def __init__(self):
        self.notificaciones_enviadas = []

    def enviar_alerta_rastreo(self, guia: str, mensaje: str, destinatario_contacto: str) -> bool:
        self.notificaciones_enviadas.append({
            "guia": guia,
            "mensaje": mensaje,
            "destinatario": destinatario_contacto,
        })
        return True


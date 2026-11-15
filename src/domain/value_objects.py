"""Value Objects del Dominio de CargoBox (Objetos de Valor Inmutables)."""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from src.domain.exceptions import DomainException, SeguroInvalidoException


@dataclass(frozen=True)
class Dinero:
    """Objeto de valor inmutable para cantidades monetarias."""
    monto: Decimal
    moneda: str = "MXN"

    def __post_init__(self):
        if not isinstance(self.monto, Decimal):
            object.__setattr__(self, "monto", Decimal(str(self.monto)))
        # Redondear a 2 decimales
        redondeado = self.monto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        object.__setattr__(self, "monto", redondeado)

    def __add__(self, other: "Dinero") -> "Dinero":
        if self.moneda != other.moneda:
            raise DomainException(f"No se pueden sumar montos en monedas distintas: {self.moneda} vs {other.moneda}")
        return Dinero(self.monto + other.monto, self.moneda)

    def __sub__(self, other: "Dinero") -> "Dinero":
        if self.moneda != other.moneda:
            raise DomainException(f"No se pueden restar montos en monedas distintas: {self.moneda} vs {other.moneda}")
        return Dinero(self.monto - other.monto, self.moneda)

    def __mul__(self, factor: Decimal | int | float) -> "Dinero":
        fact = Decimal(str(factor))
        return Dinero(self.monto * fact, self.moneda)

    def __lt__(self, other: "Dinero") -> bool:
        if self.moneda != other.moneda:
            raise DomainException("Monedas no coinciden en comparación")
        return self.monto < other.monto

    def __le__(self, other: "Dinero") -> bool:
        if self.moneda != other.moneda:
            raise DomainException("Monedas no coinciden en comparación")
        return self.monto <= other.monto

    def __gt__(self, other: "Dinero") -> bool:
        if self.moneda != other.moneda:
            raise DomainException("Monedas no coinciden en comparación")
        return self.monto > other.monto

    def __ge__(self, other: "Dinero") -> bool:
        if self.moneda != other.moneda:
            raise DomainException("Monedas no coinciden en comparación")
        return self.monto >= other.monto

    def __str__(self) -> str:
        return f"${self.monto:,.2f} {self.moneda}"


@dataclass(frozen=True)
class Dimensiones:
    """Dimensiones volumétricas en centímetros (largo, ancho, alto)."""
    largo_cm: Decimal
    ancho_cm: Decimal
    alto_cm: Decimal

    def __post_init__(self):
        for dim, val in [("largo", self.largo_cm), ("ancho", self.ancho_cm), ("alto", self.alto_cm)]:
            dec_val = Decimal(str(val))
            if dec_val <= 0:
                raise DomainException(f"La dimensión {dim} debe ser mayor a 0 cm.")
            object.__setattr__(self, f"{dim}_cm", dec_val)

    @property
    def volumen_cm3(self) -> Decimal:
        return self.largo_cm * self.ancho_cm * self.alto_cm

    @property
    def peso_volumetrico_kg(self) -> Decimal:
        """Cálculo estándar en paquetería express IATA: (Largo * Ancho * Alto) / 5000."""
        return (self.volumen_cm3 / Decimal("5000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Direccion:
    """Dirección física postal normalizada."""
    calle: str
    numero: str
    colonia: str
    ciudad: str
    codigo_postal: str
    referencias: str = ""

    def __post_init__(self):
        if not self.calle.strip() or not self.numero.strip():
            raise DomainException("Calle y número exterior son obligatorios.")
        if not self.ciudad.strip():
            raise DomainException("La ciudad es obligatoria.")
        cp_clean = self.codigo_postal.strip()
        if not re.match(r"^\d{5}$", cp_clean):
            raise DomainException(f"El código postal '{cp_clean}' debe constar de 5 dígitos numéricos.")
        object.__setattr__(self, "codigo_postal", cp_clean)

    def resumen(self) -> str:
        return f"{self.calle} #{self.numero}, Col. {self.colonia}, {self.ciudad}, CP {self.codigo_postal}"


@dataclass(frozen=True)
class Seguro:
    """Objeto de valor que representa la póliza de protección del envío."""
    amparado: bool
    valor_declarado: Decimal = Decimal("0.00")

    def __post_init__(self):
        dec_val = Decimal(str(self.valor_declarado))
        if self.amparado:
            if dec_val <= Decimal("0.00"):
                raise SeguroInvalidoException("Un envío con seguro debe tener un valor declarado mayor a $0.00 MXN.")
        else:
            if dec_val < Decimal("0.00"):
                raise SeguroInvalidoException("El valor declarado no puede ser negativo.")
        object.__setattr__(self, "valor_declarado", dec_val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    @property
    def costo_prima_mxn(self) -> Decimal:
        """Prima del seguro: 1.5% del valor declarado si está asegurado; $0 si no."""
        if not self.amparado:
            return Decimal("0.00")
        return (self.valor_declarado * Decimal("0.015")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class GuiaRastreo:
    """Código de rastreo alfanumérico único para envíos de CargoBox."""
    codigo: str

    def __post_init__(self):
        c = self.codigo.strip().upper()
        if not c or len(c) < 6:
            raise DomainException(f"Código de guía inválido: '{self.codigo}'. Longitud mínima de 6 caracteres.")
        object.__setattr__(self, "codigo", c)

    def __str__(self) -> str:
        return self.codigo


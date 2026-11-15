"""Patrón Specification con composición lógica (AND, OR, NOT) para el Dominio de CargoBox."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any


class Specification(ABC):
    """Clase base abstracta para el patrón Specification (Eric Evans & Martin Fowler)."""

    @abstractmethod
    def is_satisfied_by(self, candidate: Any) -> bool:
        """Determina si el candidato cumple con el predicado de negocio."""
        pass

    @abstractmethod
    def explain(self, candidate: Any) -> str:
        """Proporciona una justificación explicativa del cumplimiento o incumplimiento."""
        pass

    def __and__(self, other: "Specification") -> "Specification":
        return AndSpecification(self, other)

    def __or__(self, other: "Specification") -> "Specification":
        return OrSpecification(self, other)

    def __invert__(self) -> "Specification":
        return NotSpecification(self)


class AndSpecification(Specification):
    """Composición lógica AND entre dos especificaciones."""

    def __init__(self, left: Specification, right: Specification):
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: Any) -> bool:
        return self.left.is_satisfied_by(candidate) and self.right.is_satisfied_by(candidate)

    def explain(self, candidate: Any) -> str:
        left_ok = self.left.is_satisfied_by(candidate)
        right_ok = self.right.is_satisfied_by(candidate)
        left_exp = self.left.explain(candidate)
        right_exp = self.right.explain(candidate)
        if left_ok and right_ok:
            return f"CUMPLE: ({left_exp} AND {right_exp})"
        return f"NO CUMPLE: [Izquierda: {left_exp}] AND [Derecha: {right_exp}]"


class OrSpecification(Specification):
    """Composición lógica OR entre dos especificaciones."""

    def __init__(self, left: Specification, right: Specification):
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: Any) -> bool:
        return self.left.is_satisfied_by(candidate) or self.right.is_satisfied_by(candidate)

    def explain(self, candidate: Any) -> str:
        left_ok = self.left.is_satisfied_by(candidate)
        right_ok = self.right.is_satisfied_by(candidate)
        left_exp = self.left.explain(candidate)
        right_exp = self.right.explain(candidate)
        if left_ok or right_ok:
            return f"CUMPLE: ({left_exp} OR {right_exp})"
        return f"NO CUMPLE: Ninguna condición satisfecha: ({left_exp} OR {right_exp})"


class NotSpecification(Specification):
    """Composición lógica NOT (negación) de una especificación."""

    def __init__(self, spec: Specification):
        self.spec = spec

    def is_satisfied_by(self, candidate: Any) -> bool:
        return not self.spec.is_satisfied_by(candidate)

    def explain(self, candidate: Any) -> str:
        inner_ok = self.spec.is_satisfied_by(candidate)
        inner_exp = self.spec.explain(candidate)
        if not inner_ok:
            return f"CUMPLE: NOT ({inner_exp})"
        return f"NO CUMPLE: Se esperaba la negación pero se cumplió ({inner_exp})"


# ============================================================================
# ESPECIFICACIONES ATÓMICAS DE NEGOCIO
# ============================================================================

class ClienteActivoSpecification(Specification):
    """Verifica que el remitente/actor se encuentre en estado ACTIVO."""

    def is_satisfied_by(self, candidate: Any) -> bool:
        # candidate puede ser un objeto Operacion o un dict
        actor = getattr(candidate, "actor", candidate.get("actor") if isinstance(candidate, dict) else None)
        if actor is None:
            # Quizás candidate mismo tiene el atributo activo
            activo = getattr(candidate, "activo", candidate.get("activo", False) if isinstance(candidate, dict) else False)
            return bool(int(activo)) if str(activo).isdigit() else bool(activo)
        activo = getattr(actor, "activo", actor.get("activo", False) if isinstance(actor, dict) else False)
        return bool(int(activo)) if str(activo).isdigit() else bool(activo)

    def explain(self, candidate: Any) -> str:
        ok = self.is_satisfied_by(candidate)
        return "Cliente activo" if ok else "Cliente inactivo o suspendido"


class DetalleNoVacioSpecification(Specification):
    """Verifica que la operación contenga al menos una línea de detalle."""

    def is_satisfied_by(self, candidate: Any) -> bool:
        detalles = getattr(candidate, "detalles", candidate.get("detalles") if isinstance(candidate, dict) else None)
        if detalles is None:
            return False
        return len(detalles) > 0

    def explain(self, candidate: Any) -> str:
        ok = self.is_satisfied_by(candidate)
        detalles = getattr(candidate, "detalles", candidate.get("detalles", []) if isinstance(candidate, dict) else [])
        n = len(detalles) if detalles else 0
        return f"Detalle con {n} líneas" if ok else "Operación sin líneas de detalle (vacía)"


class OperacionAutorizadaSpecification(Specification):
    """Verifica que la operación cuente con la bandera o firma de autorización."""

    def is_satisfied_by(self, candidate: Any) -> bool:
        autorizado = getattr(candidate, "autorizado", candidate.get("autorizado", False) if isinstance(candidate, dict) else False)
        return bool(int(autorizado)) if str(autorizado).isdigit() else bool(autorizado)

    def explain(self, candidate: Any) -> str:
        ok = self.is_satisfied_by(candidate)
        return "Operación autorizada" if ok else "Operación no autorizada"


class ClientePreferenteSpecification(Specification):
    """Verifica si el actor es cliente preferente/VIP."""

    def is_satisfied_by(self, candidate: Any) -> bool:
        actor = getattr(candidate, "actor", candidate.get("actor") if isinstance(candidate, dict) else None)
        if actor is None:
            pref = getattr(candidate, "es_preferente", candidate.get("es_preferente", False) if isinstance(candidate, dict) else False)
            return bool(int(pref)) if str(pref).isdigit() else bool(pref)
        pref = getattr(actor, "es_preferente", actor.get("es_preferente", False) if isinstance(actor, dict) else False)
        return bool(int(pref)) if str(pref).isdigit() else bool(pref)

    def explain(self, candidate: Any) -> str:
        ok = self.is_satisfied_by(candidate)
        return "Cliente preferente (VIP)" if ok else "Cliente estándar (no preferente)"


class MontoMinimoSpecification(Specification):
    """Verifica que el importe total sea mayor o igual al monto especificado (por defecto $1,500.00 MXN)."""

    def __init__(self, monto_minimo: Decimal = Decimal("1500.00")):
        self.monto_minimo = Decimal(str(monto_minimo))

    def is_satisfied_by(self, candidate: Any) -> bool:
        total = getattr(candidate, "total_calculado", None)
        if total is None:
            # Intentar obtener total o calcularlo
            if hasattr(candidate, "calcular_total"):
                total = candidate.calcular_total()
            elif isinstance(candidate, dict):
                total = candidate.get("total", candidate.get("total_mxn", Decimal("0.00")))
            else:
                total = getattr(candidate, "total", Decimal("0.00"))
        dec_total = Decimal(str(total))
        return dec_total >= self.monto_minimo

    def explain(self, candidate: Any) -> str:
        total = getattr(candidate, "total_calculado", None)
        if total is None:
            if hasattr(candidate, "calcular_total"):
                total = candidate.calcular_total()
            elif isinstance(candidate, dict):
                total = candidate.get("total", candidate.get("total_mxn", Decimal("0.00")))
            else:
                total = getattr(candidate, "total", Decimal("0.00"))
        dec_total = Decimal(str(total))
        ok = dec_total >= self.monto_minimo
        return f"Total ${dec_total:,.2f} >= ${self.monto_minimo:,.2f}" if ok else f"Total ${dec_total:,.2f} < ${self.monto_minimo:,.2f}"


class PromocionActivaSpecification(Specification):
    """Verifica si la operación ya tiene una promoción activa asociada."""

    def is_satisfied_by(self, candidate: Any) -> bool:
        promo = getattr(candidate, "promocion_activa", candidate.get("promocion_activa", False) if isinstance(candidate, dict) else False)
        return bool(int(promo)) if str(promo).isdigit() else bool(promo)

    def explain(self, candidate: Any) -> str:
        ok = self.is_satisfied_by(candidate)
        return "Promoción ya activa" if ok else "Sin promoción activa"


class CapacidadDisponibleSpecification(Specification):
    """Verifica que los recursos solicitados cuenten con capacidad/stock suficiente."""

    def is_satisfied_by(self, candidate: Any) -> bool:
        detalles = getattr(candidate, "detalles", candidate.get("detalles", []) if isinstance(candidate, dict) else [])
        for det in detalles:
            recurso = getattr(det, "recurso", det.get("recurso") if isinstance(det, dict) else None)
            cantidad = getattr(det, "cantidad", det.get("cantidad", 0) if isinstance(det, dict) else 0)
            if recurso:
                capacidad = getattr(recurso, "capacidad_o_stock", recurso.get("capacidad_o_stock", 0) if isinstance(recurso, dict) else 0)
                habilitado = getattr(recurso, "habilitado", recurso.get("habilitado", 1) if isinstance(recurso, dict) else 1)
                if not bool(int(habilitado)) or int(capacidad) < int(cantidad):
                    return False
        return True

    def explain(self, candidate: Any) -> str:
        ok = self.is_satisfied_by(candidate)
        return "Capacidad y stock disponibles" if ok else "Capacidad excedida o recurso inhabilitado"


# ============================================================================
# COMPOSICIONES REGLAS DE NEGOCIO (LEEME / BRD / PIA)
# ============================================================================

class PuedeProcesarseSpecification(Specification):
    """Regla 1: cliente activo AND detalle no vacío AND autorización."""

    def __init__(self):
        self._composed = (
            ClienteActivoSpecification()
            & DetalleNoVacioSpecification()
            & OperacionAutorizadaSpecification()
        )

    def is_satisfied_by(self, candidate: Any) -> bool:
        return self._composed.is_satisfied_by(candidate)

    def explain(self, candidate: Any) -> str:
        return self._composed.explain(candidate)


class BeneficioReferenciaSpecification(Specification):
    """Regla 2: VIP AND total >= 1500 MXN AND NOT promoción activa."""

    def __init__(self, monto_minimo: Decimal = Decimal("1500.00")):
        self._composed = (
            ClientePreferenteSpecification()
            & MontoMinimoSpecification(monto_minimo)
            & ~PromocionActivaSpecification()
        )

    def is_satisfied_by(self, candidate: Any) -> bool:
        return self._composed.is_satisfied_by(candidate)

    def explain(self, candidate: Any) -> str:
        return self._composed.explain(candidate)


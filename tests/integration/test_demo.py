"""El script de demostración es real: cada paso se verifica contra la API."""

import importlib.util
import os

RUTA_DEMO = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "demo.py")


def _cargar_demo():
    spec = importlib.util.spec_from_file_location("demo_cargobox", RUTA_DEMO)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_demo_ejecuta_todos_los_escenarios_de_envios(client):
    demo = _cargar_demo()
    resultados = demo.ejecutar(client, incluir_operaciones=False, imprimir=lambda *_: None)
    fallidos = [descripcion for descripcion, ok in resultados if not ok]
    assert len(resultados) >= 40
    assert fallidos == []

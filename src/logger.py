"""
Módulo de logs centralizado del pipeline ETL de Airbnb Bogotá.

Expone la función ``setup_logger`` que configura un único logger compartido
por todos los módulos (extracción, transformación, carga y orquestador).
Cada ejecución genera un archivo en ``logs/`` con el formato
``log_YYYYMMDD_HHMM.txt``.
"""

import logging
from datetime import datetime
from pathlib import Path

# Carpeta logs/ en la raíz del proyecto (un nivel arriba de src/),
# independiente del directorio desde el que se ejecute el script.
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
CARPETA_LOGS = RAIZ_PROYECTO / "logs"
NOMBRE_LOGGER = "etl_airbnb"
FORMATO_LOG = "%(asctime)s - %(levelname)s - %(message)s"

def setup_logger(nombre: str = NOMBRE_LOGGER, nivel: int = logging.INFO) -> logging.Logger:
    """
    Configura y retorna el logger centralizado del proyecto.

    - Crea dinámicamente la carpeta ``logs/`` si no existe.
    - Escribe en ``logs/log_YYYYMMDD_HHMM.txt`` y también en consola.
    - Registra los niveles INFO, WARNING y ERROR (nivel mínimo INFO).
    - Es idempotente: si el logger ya tiene handlers no los duplica, de modo
      que todos los módulos comparten el mismo archivo durante una ejecución.

    Args:
        nombre: Nombre del logger. Por defecto el logger común del proyecto.
        nivel: Nivel mínimo de registro. Por defecto ``logging.INFO``.

    Returns:
        logging.Logger: Instancia de logger lista para usar.
    """
    logger = logging.getLogger(nombre)

    # Evita agregar handlers repetidos cuando varios módulos llaman a setup_logger().
    if logger.handlers:
        return logger

    logger.setLevel(nivel)
    logger.propagate = False
    formato = logging.Formatter(FORMATO_LOG)

    try:
        CARPETA_LOGS.mkdir(parents=True, exist_ok=True)
        nombre_archivo = f"log_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        file_handler = logging.FileHandler(CARPETA_LOGS / nombre_archivo, encoding="utf-8")
        file_handler.setLevel(nivel)
        file_handler.setFormatter(formato)
        logger.addHandler(file_handler)
    except OSError as error:
        # Si no se puede escribir el archivo, se continúa solo con consola.
        print(f"[logger] No fue posible crear el archivo de log: {error}")

    console_handler = logging.StreamHandler()
    console_handler.setLevel(nivel)
    console_handler.setFormatter(formato)
    logger.addHandler(console_handler)

    return logger

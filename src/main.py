"""
Orquestador del pipeline ETL de Airbnb Bogotá.

Flujo:
    1. Extrae la colección Listings de MongoDB -> normaliza precio -> limpia -> categoriza.
    2. Extrae la colección Reviews -> limpia -> procesa fechas.
    3. Carga ambos DataFrames en ``airbnb_data.db`` (SQLite) y los exporta a .xlsx
       en la raíz del proyecto.

La configuración de MongoDB se puede sobrescribir con variables de entorno:
    MONGO_URI (por defecto ``mongodb://localhost:27017/``)
    MONGO_DB  (por defecto ``airbnb``)

Ejecución (desde la raíz del proyecto):
    python src/main.py
"""

import os
import sys
import time
from pathlib import Path

from carga import Carga
from extraccion import Extraccion
from logger import setup_logger
from transformacion import Transformacion

logger = setup_logger()

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "airbnb")

COLECCION_LISTINGS = "Listings"
COLECCION_REVIEWS = "Reviews"

DB_PATH = str(RAIZ_PROYECTO / "airbnb_data.db")
EXCEL_LISTINGS = str(RAIZ_PROYECTO / "listings_transformado.xlsx")
EXCEL_REVIEWS = str(RAIZ_PROYECTO / "reviews_transformado.xlsx")

def procesar_listings(extractor: Extraccion, transformador: Transformacion):
    """
    Extrae y transforma la colección Listings.

    Orden: normalizar precio -> limpiar nulos/duplicados (price es crítico) -> categorizar.
    El precio se normaliza antes de limpiar para que los valores no convertibles
    queden como NaN y se traten como nulos críticos.

    Returns:
        pd.DataFrame: Listings transformado.
    """
    logger.info("=== Procesando Listings ===")
    df = extractor.extraer_coleccion(COLECCION_LISTINGS)
    df = transformador.normalizar_precio(df, "price")
    df = transformador.limpiar_nulos_y_duplicados(df, columnas_criticas=["price"])
    df = transformador.categorizar_precios(df, "price")
    return df

def procesar_reviews(extractor: Extraccion, transformador: Transformacion):
    """
    Extrae y transforma la colección Reviews.

    Orden: limpiar nulos/duplicados (date es crítica) -> procesar fechas.

    Returns:
        pd.DataFrame: Reviews transformado.
    """
    logger.info("=== Procesando Reviews ===")
    df = extractor.extraer_coleccion(COLECCION_REVIEWS)
    df = transformador.limpiar_nulos_y_duplicados(df, columnas_criticas=["date"])
    df = transformador.procesar_fechas(df, "date")
    return df

def ejecutar_pipeline() -> None:
    """Ejecuta el pipeline ETL completo: extracción, transformación y carga."""
    inicio = time.perf_counter()
    logger.info("========== INICIO DEL PIPELINE ETL AIRBNB BOGOTÁ ==========")

    transformador = Transformacion()
    cargador = Carga()

    # Extracción + Transformación (la conexión se cierra al salir del bloque with).
    with Extraccion(MONGO_URI, MONGO_DB) as extractor:
        df_listings = procesar_listings(extractor, transformador)
        df_reviews = procesar_reviews(extractor, transformador)

    # Carga
    logger.info("=== Cargando resultados ===")
    cargador.cargar_sqlite(df_listings, "listings", DB_PATH)
    cargador.cargar_sqlite(df_reviews, "reviews", DB_PATH)
    cargador.exportar_excel(df_listings, EXCEL_LISTINGS)
    cargador.exportar_excel(df_reviews, EXCEL_REVIEWS)

    duracion = time.perf_counter() - inicio
    logger.info(f"========== PIPELINE FINALIZADO CON ÉXITO en {duracion:.2f} s ==========")

if __name__ == "__main__":
    try:
        ejecutar_pipeline()
    except KeyboardInterrupt:
        logger.warning("Ejecución interrumpida por el usuario.")
        sys.exit(130)
    except Exception as error:
        logger.error(f"El pipeline ETL falló: {type(error).__name__}: {error}", exc_info=True)
        sys.exit(1)

"""
Módulo de Pruebas Automatizadas de Calidad de Datos (QA) para el Pipeline ETL de Airbnb Bogotá.

Este archivo valida los entregables y requisitos del taller universitario:
1. Estructura física del repositorio y existencia de archivos requeridos.
2. Extracción real desde MongoDB local (validando base de datos y colecciones).
3. Lógica de transformaciones críticas (limpieza, normalización, fechas y categorías).
4. Carga de datos en SQLite y exportación a archivos Excel (.xlsx).
5. Sistema de logging centralizado y formato de logs.
"""

import os
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
import pytest

# Asegurar que el directorio raíz y src estén en el PYTHONPATH para importar módulos
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROYECTO))
sys.path.insert(0, str(RAIZ_PROYECTO / "src"))

from src.carga import Carga
from src.extraccion import Extraccion
from src.logger import setup_logger
from src.transformacion import Transformacion

# ==============================================================================
# 1. TEST DE ESTRUCTURA DEL REPOSITORIO Y ENTREGABLES
# ==============================================================================
def test_estructura_archivos():
    """
    RÚBRICA ITEM 1: Integridad del proyecto y entregables obligatorios.
    Verifica que existan físicamente los archivos y carpetas clave en la raíz
    y en los subdirectorios indicados.
    """
    elementos_obligatorios = [
        RAIZ_PROYECTO / "src" / "extraccion.py",
        RAIZ_PROYECTO / "src" / "transformacion.py",
        RAIZ_PROYECTO / "src" / "carga.py",
        RAIZ_PROYECTO / "notebooks" / "exploracion_airbnb.ipynb",
        RAIZ_PROYECTO / "logs",
        RAIZ_PROYECTO / "README.md",
        RAIZ_PROYECTO / "requirements.txt",
    ]

    for ruta in elementos_obligatorios:
        assert ruta.exists(), f"El entregable obligatorio no existe: {ruta}"
        if ruta.name == "logs":
            assert ruta.is_dir(), f"'{ruta}' debe ser un directorio."
        else:
            assert ruta.is_file(), f"'{ruta}' debe ser un archivo."
            assert ruta.stat().st_size > 0, f"'{ruta}' está vacío."

# ==============================================================================
# 2. TEST DE EXTRACCIÓN Y MONGODB (CONEXIÓN REAL)
# ==============================================================================
def test_extraccion_mongodb():
    """
    RÚBRICA ITEM 2: Conexión y Extracción de MongoDB local.
    Verifica la conexión al servidor MongoDB local, la existencia de las 3
    colecciones requeridas ('Listings', 'Reviews', 'Calendar') no vacías, y
    que el método extraer_coleccion() devuelva un DataFrame de pandas con registros.
    """
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    mongo_db = os.getenv("MONGO_DB", "airbnb_bogota")

    try:
        extractor = Extraccion(uri=mongo_uri, db_name=mongo_db, timeout_ms=3000)
    except Exception as e:
        pytest.fail(
            f"Fallo al conectar a MongoDB local en '{mongo_uri}' con la BD '{mongo_db}'. "
            f"Asegúrate de que MongoDB esté corriendo y con los datos cargados. Error: {e}"
        )

    with extractor:
        # Validar existencia de colecciones requeridas (insensible a mayúsculas/minúsculas)
        colecciones_disponibles = extractor.db.list_collection_names()
        colecciones_requeridas = ["Listings", "Reviews", "Calendar"]

        for coleccion in colecciones_requeridas:
            nombres_coincidentes = [
                col for col in colecciones_disponibles if col.lower() == coleccion.lower()
            ]
            assert nombres_coincidentes, (
                f"La colección '{coleccion}' no existe en la base de datos '{mongo_db}'. "
                f"Colecciones encontradas: {colecciones_disponibles}"
            )

            # Validar que no esté vacía
            conteo_documentos = extractor.db[nombres_coincidentes[0]].count_documents({})
            assert conteo_documentos > 0, (
                f"La colección '{nombres_coincidentes[0]}' está vacía. Se requieren registros para el pipeline."
            )

        # Probar el método de extracción (obteniendo una muestra de Listings)
        df_listings = extractor.extraer_coleccion("Listings", limite=50)
        assert isinstance(
            df_listings, pd.DataFrame
        ), "extraer_coleccion debe retornar una instancia de pandas.DataFrame."
        assert len(df_listings) > 0, "El DataFrame extraído de Listings debe contener más de 0 filas."
        assert len(df_listings.columns) > 0, "El DataFrame extraído debe contener columnas."

# ==============================================================================
# 3. TEST DE TRANSFORMACIONES DE DATOS (MOCK / RÁPIDO)
# ==============================================================================
@pytest.fixture
def mock_airbnb_data():
    """Fixture que genera un DataFrame con datos sucios típicos de Airbnb."""
    return pd.DataFrame(
        {
            "_id": ["doc1", "doc2", "doc3", "doc4", "doc5"],
            "id": [101, 102, 102, 103, 104],  # 102 repetido (duplicado)
            "name": ["Apartamento Chapinero", None, None, "Loft Usaquén", "Casa Histórica"],
            "price": ["$1,250.00", "$500.50", "$500.50", None, "$3,400.00"],
            "date": ["2023-10-11", "2023-10-12", "2023-10-12", "2023-11-05", "fecha_invalida"],
            "minimum_nights": [2, np.nan, np.nan, 3, 5],
            "amenities": [
                '["Wifi", "Cocina"]',
                '["TV", "Parqueadero"]',
                '["TV", "Parqueadero"]',
                ["Wifi", "Piscina"],  # Objeto anidado real (lista de python)
                '["Ascensor"]',
            ],
            "license": [None, None, None, None, None],  # 100% nulo
        }
    )

def test_transformaciones_obligatorias(mock_airbnb_data):
    """
    RÚBRICA ITEM 3: Transformaciones y reglas de negocio con Pandas.
    Valida la normalización de precios, eliminación de duplicados, manejo de nulos,
    procesamiento de fechas y generación de variables derivadas/categóricas.
    """
    transformador = Transformacion()
    df = mock_airbnb_data.copy()
    total_filas_iniciales = len(df)

    # 1. Normalización de precios
    df = transformador.normalizar_precio(df, columna="price")
    assert pd.api.types.is_float_dtype(
        df["price"]
    ), "La columna 'price' debe ser de tipo float tras la normalización."
    # Comprobar que no contenga caracteres de formato monetario
    assert df["price"].dropna().isin([1250.0, 500.50, 3400.0]).any()

    # 2. Limpieza de duplicados y nulos críticos
    df = transformador.limpiar_nulos_y_duplicados(df, columnas_criticas=["price"])
    assert len(df) < total_filas_iniciales, "Debieron removerse duplicados y/o filas con precio nulo."
    assert df["price"].isnull().sum() == 0, "No deben quedar valores nulos en la columna crítica 'price'."
    assert not df.duplicated(
        subset=["id"]
    ).any(), "No deben quedar registros duplicados basados en 'id'."
    assert "license" not in df.columns, "Las columnas con > 90% de nulos deben ser descartadas."

    # 3. Procesamiento y derivación de fechas
    df = transformador.procesar_fechas(df, columna_fecha="date")
    columnas_derivadas = ["anio", "mes", "dia", "trimestre"]
    for col in columnas_derivadas:
        assert (
            col in df.columns
        ), f"La columna derivada obligatoria '{col}' no se encuentra en el DataFrame."

    assert pd.api.types.is_datetime64_any_dtype(
        df["date"]
    ), "La columna 'date' debe ser de tipo datetime64."
    # Verificar cálculo correcto
    primera_fila = df.iloc[0]
    assert primera_fila["anio"] == 2023
    assert primera_fila["mes"] == 10
    assert primera_fila["dia"] == 11
    assert primera_fila["trimestre"] == 4

    # 4. Categorización de precios
    df = transformador.categorizar_precios(
        df,
        columna_precio="price",
        bins=[0, 800, 2000, 10000],
        etiquetas=["Económico", "Estándar", "Premium"],
    )
    assert (
        "categoria_precio" in df.columns
    ), "La columna 'categoria_precio' debe ser generada por el transformador."
    assert set(df["categoria_precio"].dropna().unique()).issubset(
        {"Económico", "Estándar", "Premium"}
    ), "Los valores asignados deben coincidir con las categorías configuradas."

# ==============================================================================
# 4. TEST DE CARGA EN SQLITE Y EXCEL
# ==============================================================================
def test_carga_datos(tmp_path):
    """
    RÚBRICA ITEM 4: Persistencia en base de datos relacional y hojas de cálculo.
    Valida la inserción correcta en SQLite verificando el conteo de registros,
    y la exportación válida a formato Excel (.xlsx).
    """
    cargador = Carga()

    # DataFrame limpio para prueba de carga
    df_para_cargar = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "name": ["Apto 1", "Apto 2", "Apto 3"],
            "price": [120000.0, 350000.0, 950000.0],
            "categoria_precio": ["Económico", "Estándar", "Premium"],
            "date": pd.to_datetime(["2023-01-10", "2023-02-15", "2023-03-20"]),
            "tags": [["wifi", "balcon"], ["tv"], ["vista"]],  # Estructura anidada para serializar
        }
    )

    # 1. Prueba de Carga en SQLite
    db_test_path = str(tmp_path / "test_airbnb.db")
    nombre_tabla = "listings_test"
    filas_cargadas = cargador.cargar_sqlite(df_para_cargar, nombre_tabla, db_test_path)

    assert os.path.exists(db_test_path), f"El archivo SQLite no fue creado en: {db_test_path}"
    assert filas_cargadas == len(
        df_para_cargar
    ), f"El método debe retornar {len(df_para_cargar)} filas insertadas."

    # Validar directamente con conexión sqlite3
    with sqlite3.connect(db_test_path) as conn:
        cursor = conn.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM "{nombre_tabla}"')
        count_real = cursor.fetchone()[0]
        assert count_real == len(
            df_para_cargar
        ), f"El conteo en SQLite ({count_real}) no coincide con el DataFrame ({len(df_para_cargar)})."

    # 2. Prueba de Exportación a Excel
    excel_test_path = str(tmp_path / "test_listings.xlsx")
    cargador.exportar_excel(df_para_cargar, excel_test_path)

    assert os.path.exists(excel_test_path), f"El archivo Excel no fue generado en: {excel_test_path}"
    assert os.path.getsize(excel_test_path) > 0, "El archivo Excel generado está vacío."

    # Comprobar que openpyxl pueda leerlo correctamente
    wb = openpyxl.load_workbook(excel_test_path)
    sheet = wb.active
    # Filas totales = encabezado + registros
    assert (
        sheet.max_row == len(df_para_cargar) + 1
    ), f"El Excel debe tener {len(df_para_cargar) + 1} filas incluyendo el encabezado."

# ==============================================================================
# 5. TEST DE MANEJO DE LOGS CENTRALIZADO
# ==============================================================================
def test_sistema_logs():
    """
    RÚBRICA ITEM 5: Observabilidad y trazabilidad con módulo de Logging.
    Verifica que la carpeta logs/ exista, que los nombres sigan el formato
    log_YYYYMMDD_HHMM.txt y que registren timestamps con niveles INFO, WARNING o ERROR.
    """
    logger = setup_logger()
    logger.info("Test de verificación de QA ejecutado exitosamente.")

    carpeta_logs = RAIZ_PROYECTO / "logs"
    assert carpeta_logs.exists() and carpeta_logs.is_dir(), "El directorio 'logs/' debe existir."

    archivos_log = list(carpeta_logs.glob("*.txt"))
    assert len(archivos_log) > 0, "No se encontraron archivos de log en la carpeta 'logs/'."

    patron_nombre_log = re.compile(r"^log_\d{8}_\d{4}\.txt$")
    coincidencias = [f for f in archivos_log if patron_nombre_log.match(f.name)]
    assert (
        len(coincidencias) > 0
    ), f"Ningún archivo de log cumple con el formato 'log_YYYYMMDD_HHMM.txt'. Encontrados: {[f.name for f in archivos_log]}"

    # Inspeccionar el log más reciente
    log_reciente = max(archivos_log, key=lambda f: f.stat().st_mtime)
    assert log_reciente.stat().st_size > 0, f"El archivo de log {log_reciente.name} está vacío."

    contenido = log_reciente.read_text(encoding="utf-8")
    assert any(
        nivel in contenido for nivel in ["INFO", "WARNING", "ERROR"]
    ), "El archivo de log debe contener al menos un registro con nivel INFO, WARNING o ERROR."

    # Validar formato: %(asctime)s - %(levelname)s - %(message)s
    # Ejemplo: 2026-10-10 15:48:49,545 - INFO - ...
    patron_linea_log = re.compile(
        r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d+)?\s+-\s+(INFO|WARNING|ERROR)\s+-\s+.+"
    )
    assert patron_linea_log.search(
        contenido
    ), "El log no cumple con el formato estándar '%(asctime)s - %(levelname)s - %(message)s'."

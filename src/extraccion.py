"""
Módulo de extracción del pipeline ETL.

Contiene la clase ``Extraccion``, responsable de conectarse a MongoDB local
y convertir colecciones en DataFrames de Pandas.
"""

from typing import Optional

import pandas as pd
from pymongo import MongoClient
from pymongo.errors import (ConnectionFailure, PyMongoError,
                            ServerSelectionTimeoutError)

from logger import setup_logger

logger = setup_logger()

class Extraccion:
    """
    Extrae colecciones de una base de datos MongoDB y las retorna como DataFrames.

    Attributes:
        uri (str): Cadena de conexión a MongoDB.
        db_name (str): Nombre de la base de datos.
        client (MongoClient): Cliente de pymongo.
        db (Database): Referencia a la base de datos.
    """

    def __init__(self, uri: str, db_name: str, timeout_ms: int = 5000):
        """
        Establece la conexión con MongoDB y verifica que el servidor responda.

        Args:
            uri: Cadena de conexión, por ejemplo ``mongodb://localhost:27017/``.
            db_name: Nombre de la base de datos que contiene las colecciones.
            timeout_ms: Tiempo máximo de espera para seleccionar el servidor.

        Raises:
            ConnectionFailure: Si el servidor de MongoDB no está disponible.
        """
        self.uri = uri
        self.db_name = db_name
        self.client: Optional[MongoClient] = None
        self.db = None

        try:
            logger.info(f"Conectando a MongoDB en '{uri}' (base de datos: '{db_name}')...")
            self.client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
            # 'ping' fuerza la conexión real; MongoClient es perezoso por defecto.
            self.client.admin.command("ping")
            self.db = self.client[db_name]
            logger.info("Conexión a MongoDB establecida correctamente.")

            if db_name not in self.client.list_database_names():
                logger.warning(f"La base de datos '{db_name}' no existe o está vacía en el servidor.")
        except (ServerSelectionTimeoutError, ConnectionFailure) as error:
            logger.error(f"No fue posible conectar con MongoDB: {error}")
            raise
        except PyMongoError as error:
            logger.error(f"Error de pymongo durante la conexión: {error}")
            raise

    def _resolver_nombre_coleccion(self, nombre_coleccion: str) -> str:
        """
        Busca la colección por nombre exacto y, si no existe, intenta una
        coincidencia sin distinguir mayúsculas/minúsculas (ej. 'Listings' vs 'listings').

        Args:
            nombre_coleccion: Nombre solicitado.

        Returns:
            str: Nombre real de la colección en MongoDB.

        Raises:
            ValueError: Si la colección no existe.
        """
        disponibles = self.db.list_collection_names()
        if nombre_coleccion in disponibles:
            return nombre_coleccion

        for nombre in disponibles:
            if nombre.lower() == nombre_coleccion.lower():
                logger.warning(f"Colección '{nombre_coleccion}' no encontrada; se usará '{nombre}'.")
                return nombre

        raise ValueError(
            f"La colección '{nombre_coleccion}' no existe en '{self.db_name}'. "
            f"Colecciones disponibles: {disponibles}"
        )

    def extraer_coleccion(self, nombre_coleccion: str, limite: Optional[int] = None) -> pd.DataFrame:
        """
        Lee una colección de MongoDB y la convierte en un DataFrame.
        El campo ``_id`` (ObjectId) se convierte a texto para que pueda
        almacenarse posteriormente en SQLite/Excel.
        Args: nombre_coleccion: Nombre de la colección (Listings, Reviews, Calendar).            limite: Número máximo de documentos a leer (útil para pruebas). ``None`` = todos.

        Returns:
            pd.DataFrame: Datos de la colección (vacío si no hay documentos).

        Raises:
            ValueError: Si la colección no existe.
            PyMongoError: Si ocurre un error durante la lectura.
        """
        try:
            nombre_real = self._resolver_nombre_coleccion(nombre_coleccion)
            logger.info(f"Extrayendo colección '{nombre_real}'...")

            cursor = self.db[nombre_real].find({})
            if limite:
                cursor = cursor.limit(int(limite))
                logger.warning(f"Extracción de '{nombre_real}' limitada a {limite} documentos.")

            df = pd.DataFrame(list(cursor))

            if df.empty:
                logger.warning(f"La colección '{nombre_real}' no contiene documentos.")
                return df

            if "_id" in df.columns:
                df["_id"] = df["_id"].astype(str)

            logger.info(
                f"Colección '{nombre_real}': {len(df)} registros extraídos "
                f"({df.shape[1]} columnas)."
            )
            return df
        except ValueError as error:
            logger.error(str(error))
            raise
        except PyMongoError as error:
            logger.error(f"Error al leer la colección '{nombre_coleccion}': {error}")
            raise

    def cerrar_conexion(self) -> None:
        """Cierra la conexión con MongoDB si está abierta."""
        if self.client is not None:
            self.client.close()
            logger.info("Conexión a MongoDB cerrada.")

    def __enter__(self):
        """Permite usar la clase como context manager (``with Extraccion(...) as ext``)."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cierra la conexión al salir del bloque ``with``."""
        self.cerrar_conexion()

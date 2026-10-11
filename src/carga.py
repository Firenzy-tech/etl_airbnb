"""
Módulo de carga del pipeline ETL.

Contiene la clase ``Carga``, encargada de persistir los DataFrames
transformados en SQLite y en archivos Excel (.xlsx).
"""

import json
import sqlite3
from pathlib import Path

import pandas as pd
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from logger import setup_logger

logger = setup_logger()

# Límite de filas de una hoja de Excel (incluye la fila de encabezado).
MAX_FILAS_EXCEL = 1_048_576


class Carga:
    """Carga DataFrames en SQLite y los exporta a Excel."""

    @staticmethod
    def _serializar_valor(valor):
        """Convierte listas/diccionarios (campos anidados de MongoDB) en texto JSON."""
        if isinstance(valor, (list, dict, set, tuple)):
            return json.dumps(list(valor) if isinstance(valor, set) else valor, ensure_ascii=False, default=str)
        return valor

    def _preparar_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepara una copia del DataFrame para su almacenamiento:

        - Serializa estructuras anidadas (listas/diccionarios) a JSON.
        - Convierte las columnas datetime a texto ``YYYY-MM-DD``.

        Args:
            df: DataFrame original.

        Returns:
            pd.DataFrame: Copia lista para SQLite/Excel.
        """
        df = df.copy()
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime("%Y-%m-%d")
            elif pd.api.types.is_object_dtype(df[col]):
                df[col] = df[col].map(self._serializar_valor)
        return df

    def cargar_sqlite(self, df: pd.DataFrame, nombre_tabla: str, db_path: str) -> int:
        """
        Guarda el DataFrame en una tabla SQLite reemplazándola si existe.

        Args:
            df: DataFrame a cargar.
            nombre_tabla: Nombre de la tabla destino.
            db_path: Ruta del archivo de base de datos SQLite.

        Returns:
            int: Número de filas insertadas.

        Raises:
            sqlite3.Error: Si ocurre un error en la base de datos.
        """
        conexion = None
        try:
            if df.empty:
                logger.warning(f"El DataFrame para la tabla '{nombre_tabla}' está vacío; se creará vacía.")

            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            datos = self._preparar_dataframe(df)

            conexion = sqlite3.connect(db_path)
            datos.to_sql(nombre_tabla, conexion, if_exists="replace", index=False, chunksize=10_000)
            conexion.commit()

            filas = conexion.execute(f'SELECT COUNT(*) FROM "{nombre_tabla}"').fetchone()[0]
            logger.info(f"Tabla '{nombre_tabla}' cargada en '{db_path}': {filas} filas insertadas.")
            return filas
        except sqlite3.Error as error:
            logger.error(f"Error de SQLite al cargar la tabla '{nombre_tabla}': {error}")
            raise
        except Exception as error:
            logger.error(f"Error inesperado al cargar la tabla '{nombre_tabla}': {error}")
            raise
        finally:
            if conexion is not None:
                conexion.close()

    def exportar_excel(self, df: pd.DataFrame, ruta_archivo: str) -> None:
        """
        Exporta el DataFrame a un archivo .xlsx sin índice.

        - Elimina caracteres de control no permitidos por Excel (comunes en
          los comentarios de Reviews).
        - Si el DataFrame supera el límite de filas de Excel, se trunca y se
          registra una advertencia (la tabla completa queda en SQLite).

        Args:
            df: DataFrame a exportar.
            ruta_archivo: Ruta del archivo .xlsx destino.

        Raises:
            OSError: Si el archivo no se puede escribir (p. ej. está abierto en Excel).
        """
        try:
            ruta = Path(ruta_archivo)
            ruta.parent.mkdir(parents=True, exist_ok=True)
            datos = self._preparar_dataframe(df)

            limite = MAX_FILAS_EXCEL - 1
            if len(datos) > limite:
                logger.warning(
                    f"El DataFrame tiene {len(datos)} filas y supera el límite de Excel; "
                    f"se exportarán solo las primeras {limite}."
                )
                datos = datos.head(limite)

            columnas_texto = [
                col for col in datos.columns
                if pd.api.types.is_object_dtype(datos[col]) or pd.api.types.is_string_dtype(datos[col])
            ]
            for col in columnas_texto:
                datos[col] = datos[col].map(
                    lambda v: ILLEGAL_CHARACTERS_RE.sub("", v) if isinstance(v, str) else v
                )

            datos.to_excel(ruta, index=False, engine="openpyxl")
            logger.info(f"Archivo Excel exportado: '{ruta}' ({len(datos)} filas).")
        except PermissionError as error:
            logger.error(f"No se pudo escribir '{ruta_archivo}' (¿está abierto en otro programa?): {error}")
            raise
        except Exception as error:
            logger.error(f"Error al exportar '{ruta_archivo}' a Excel: {error}")
            raise


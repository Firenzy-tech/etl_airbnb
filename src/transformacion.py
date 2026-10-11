"""
Módulo de transformación del pipeline ETL.

Contiene la clase ``Transformacion`` con las operaciones de limpieza,
normalización de precios, procesamiento de fechas y categorización.
Todos los métodos trabajan sobre una copia del DataFrame recibido.
"""

from typing import Iterable, List, Optional

import numpy as np
import pandas as pd

from logger import setup_logger

logger = setup_logger()

VALOR_TEXTO_NULO = "Sin información"

class Transformacion:
    """Agrupa las transformaciones aplicadas a los datos de Airbnb Bogotá."""

    @staticmethod
    def _validar_columna(df: pd.DataFrame, columna: str) -> None:
        """
        Verifica que la columna exista en el DataFrame.

        Raises:
            KeyError: Si la columna no existe.
        """
        if columna not in df.columns:
            mensaje = f"La columna '{columna}' no existe en el DataFrame."
            logger.error(mensaje)
            raise KeyError(mensaje)

    @staticmethod
    def _columnas_no_hashables(df: pd.DataFrame) -> List[str]:
        """
        Detecta columnas con listas, diccionarios o conjuntos (frecuentes en
        documentos de MongoDB) que impiden usar ``drop_duplicates`` directamente.
        """
        columnas = []
        for col in df.columns:
            if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
                muestra = df[col].dropna()
                if muestra.map(lambda v: isinstance(v, (list, dict, set))).any():
                    columnas.append(col)
        return columnas

    def limpiar_nulos_y_duplicados(
        self,
        df: pd.DataFrame,
        columnas_criticas: Optional[Iterable[str]] = None,
        umbral_nulos_columna: float = 0.9,
        excluir_relleno: Optional[Iterable[str]] = None,
    ) -> pd.DataFrame:
        """
        Elimina duplicados y trata los valores nulos con la siguiente lógica:

        1. Elimina filas duplicadas (ignorando ``_id``, que siempre es único).
        2. Elimina columnas cuyo porcentaje de nulos supera ``umbral_nulos_columna``.
        3. Elimina filas con nulos en ``columnas_criticas`` (ej. ``price``, ``date``).
        4. Imputa columnas numéricas con la mediana y columnas de texto con
           ``'Sin información'``. Las columnas en ``excluir_relleno`` se dejan intactas.

        Args:
            df: DataFrame de entrada.
            columnas_criticas: Columnas donde un nulo invalida la fila.
            umbral_nulos_columna: Proporción (0-1) de nulos a partir de la cual se elimina la columna.
            excluir_relleno: Columnas que no deben imputarse (ej. fechas).

        Returns:
            pd.DataFrame: DataFrame limpio.
        """
        try:
            df = df.copy()
            filas_iniciales = len(df)
            logger.info(f"Limpieza iniciada: {filas_iniciales} filas, {df.shape[1]} columnas.")

            if df.empty:
                logger.warning("El DataFrame está vacío; no se aplica limpieza.")
                return df

            # 1. Duplicados (las columnas no hashables se comparan como texto).
            subset = [c for c in df.columns if c != "_id"]
            no_hashables = self._columnas_no_hashables(df)
            if no_hashables:
                logger.warning(f"Columnas con estructuras anidadas (se comparan como texto): {no_hashables}")
                comparacion = df[subset].copy()
                for col in no_hashables:
                    comparacion[col] = comparacion[col].astype(str)
                mascara_dup = comparacion.duplicated()
            else:
                mascara_dup = df.duplicated(subset=subset)

            duplicados = int(mascara_dup.sum())
            df = df[~mascara_dup]
            if duplicados:
                logger.warning(f"Se eliminaron {duplicados} filas duplicadas.")
            else:
                logger.info("No se encontraron filas duplicadas.")

            # 2. Columnas casi vacías.
            proporcion_nulos = df.isnull().mean()
            columnas_vacias = proporcion_nulos[proporcion_nulos > umbral_nulos_columna].index.tolist()
            criticas = list(columnas_criticas or [])
            columnas_vacias = [c for c in columnas_vacias if c not in criticas]
            if columnas_vacias:
                df = df.drop(columns=columnas_vacias)
                logger.warning(
                    f"Se eliminaron {len(columnas_vacias)} columnas con más del "
                    f"{umbral_nulos_columna:.0%} de nulos: {columnas_vacias}"
                )

            # 3. Filas con nulos en columnas críticas.
            criticas_presentes = [c for c in criticas if c in df.columns]
            faltantes = set(criticas) - set(criticas_presentes)
            if faltantes:
                logger.warning(f"Columnas críticas no encontradas: {sorted(faltantes)}")
            if criticas_presentes:
                antes = len(df)
                df = df.dropna(subset=criticas_presentes)
                eliminadas = antes - len(df)
                if eliminadas:
                    logger.warning(
                        f"Se eliminaron {eliminadas} filas con nulos en columnas críticas {criticas_presentes}."
                    )

            # 4. Imputación del resto de nulos.
            excluidas = set(excluir_relleno or []) | set(criticas_presentes)
            for col in df.columns:
                if col in excluidas:
                    continue
                nulos = int(df[col].isnull().sum())
                if nulos == 0:
                    continue
                if pd.api.types.is_bool_dtype(df[col]):
                    continue
                if pd.api.types.is_numeric_dtype(df[col]):
                    mediana = df[col].median()
                    df[col] = df[col].fillna(mediana)
                    logger.info(f"Columna '{col}': {nulos} nulos imputados con la mediana ({mediana}).")
                elif pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
                    df[col] = df[col].fillna(VALOR_TEXTO_NULO)
                    logger.info(f"Columna '{col}': {nulos} nulos imputados con '{VALOR_TEXTO_NULO}'.")

            df = df.reset_index(drop=True)
            logger.info(
                f"Limpieza finalizada: filas antes = {filas_iniciales}, filas después = {len(df)} "
                f"(eliminadas: {filas_iniciales - len(df)})."
            )
            return df
        except Exception as error:
            logger.error(f"Error en limpiar_nulos_y_duplicados: {error}")
            raise

    def normalizar_precio(self, df: pd.DataFrame, columna: str) -> pd.DataFrame:
        """
        Elimina los símbolos ``$`` y las comas de la columna de precio y la
        convierte a ``float``. Los valores no convertibles quedan como NaN.

        Ejemplo: ``"$1,250,000.00"`` -> ``1250000.0``.

        Args:
            df: DataFrame de entrada.
            columna: Nombre de la columna de precio.

        Returns:
            pd.DataFrame: DataFrame con la columna de precio en float.
        """
        try:
            self._validar_columna(df, columna)
            df = df.copy()
            nulos_antes = int(df[columna].isnull().sum())

            if pd.api.types.is_numeric_dtype(df[columna]):
                logger.info(f"La columna '{columna}' ya es numérica; solo se convierte a float.")
                df[columna] = df[columna].astype(float)
                return df

            limpia = (
                df[columna]
                .astype("string")
                .str.replace("$", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            df[columna] = pd.to_numeric(limpia, errors="coerce").astype(float)

            nuevos_nulos = int(df[columna].isnull().sum()) - nulos_antes
            if nuevos_nulos > 0:
                logger.warning(f"Columna '{columna}': {nuevos_nulos} valores no pudieron convertirse a float (NaN).")

            negativos = int((df[columna] < 0).sum())
            if negativos:
                logger.warning(f"Columna '{columna}': {negativos} precios negativos detectados.")

            logger.info(
                f"Columna '{columna}' normalizada a float "
                f"(nulos totales: {int(df[columna].isnull().sum())})."
            )
            return df
        except KeyError:
            raise
        except Exception as error:
            logger.error(f"Error en normalizar_precio('{columna}'): {error}")
            raise

    def procesar_fechas(self, df: pd.DataFrame, columna_fecha: str) -> pd.DataFrame:
        """
        Convierte la columna a datetime con formato ``YYYY-MM-DD`` (sin hora)
        y crea las columnas derivadas ``anio``, ``mes``, ``dia`` y ``trimestre``.
        Las filas con fechas inválidas se eliminan y se registran como advertencia.

        Args:
            df: DataFrame de entrada.
            columna_fecha: Nombre de la columna de fecha.

        Returns:
            pd.DataFrame: DataFrame con la fecha normalizada y columnas derivadas.
        """
        try:
            self._validar_columna(df, columna_fecha)
            df = df.copy()

            fechas = pd.to_datetime(df[columna_fecha], errors="coerce")
            if getattr(fechas.dt, "tz", None) is not None:
                fechas = fechas.dt.tz_localize(None)
            df[columna_fecha] = fechas.dt.normalize()

            invalidas = int(df[columna_fecha].isnull().sum())
            if invalidas:
                logger.warning(
                    f"Columna '{columna_fecha}': {invalidas} fechas inválidas o nulas; se eliminan esas filas."
                )
                df = df.dropna(subset=[columna_fecha]).reset_index(drop=True)

            df["anio"] = df[columna_fecha].dt.year
            df["mes"] = df[columna_fecha].dt.month
            df["dia"] = df[columna_fecha].dt.day
            df["trimestre"] = df[columna_fecha].dt.quarter

            if not df.empty:
                logger.info(
                    f"Columna '{columna_fecha}' procesada. Rango: "
                    f"{df[columna_fecha].min():%Y-%m-%d} a {df[columna_fecha].max():%Y-%m-%d}. "
                    "Columnas derivadas: anio, mes, dia, trimestre."
                )
            return df
        except KeyError:
            raise
        except Exception as error:
            logger.error(f"Error en procesar_fechas('{columna_fecha}'): {error}")
            raise

    def categorizar_precios(
        self,
        df: pd.DataFrame,
        columna_precio: str,
        bins: Optional[List[float]] = None,
        etiquetas: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Crea la columna ``categoria_precio`` usando ``pd.cut``.

        Si no se indican ``bins``, los cortes se calculan con los percentiles
        33 y 66 de los datos (los precios de Bogotá están en COP, por lo que
        unos límites fijos dependerían de la moneda y la temporada).

        Args:
            df: DataFrame de entrada (con la columna de precio ya en float).
            columna_precio: Nombre de la columna de precio.
            bins: Límites personalizados (len = len(etiquetas) + 1).
            etiquetas: Nombres de las categorías. Por defecto Económico, Estándar, Premium.

        Returns:
            pd.DataFrame: DataFrame con la columna ``categoria_precio``.
        """
        try:
            self._validar_columna(df, columna_precio)
            df = df.copy()
            etiquetas = etiquetas or ["Económico", "Estándar", "Premium"]

            if not pd.api.types.is_numeric_dtype(df[columna_precio]):
                raise TypeError(
                    f"La columna '{columna_precio}' no es numérica. Ejecute normalizar_precio() primero."
                )

            if bins is None:
                p33, p66 = df[columna_precio].quantile([0.33, 0.66]).tolist()
                bins = [-np.inf, p33, p66, np.inf]
                logger.info(f"Cortes de precio calculados por percentiles: P33 = {p33:,.2f}, P66 = {p66:,.2f}.")

            if len(bins) != len(etiquetas) + 1:
                raise ValueError("La cantidad de bins debe ser igual a la cantidad de etiquetas + 1.")
            if any(b2 <= b1 for b1, b2 in zip(bins, bins[1:])):
                raise ValueError(f"Los límites de los bins deben ser estrictamente crecientes: {bins}")

            df["categoria_precio"] = pd.cut(
                df[columna_precio], bins=bins, labels=etiquetas, include_lowest=True
            ).astype("object")

            sin_categoria = int(df["categoria_precio"].isnull().sum())
            if sin_categoria:
                logger.warning(f"{sin_categoria} registros quedaron sin categoría de precio (precio nulo).")

            distribucion = df["categoria_precio"].value_counts().to_dict()
            logger.info(f"Columna 'categoria_precio' creada. Distribución: {distribucion}")
            return df
        except KeyError:
            raise
        except Exception as error:
            logger.error(f"Error en categorizar_precios('{columna_precio}'): {error}")
            raise

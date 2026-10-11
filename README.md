# Proceso ETL con datasets de Airbnb Bogotá

Pipeline ETL en Python que extrae datos de Airbnb Bogotá desde **MongoDB**, los transforma con **Pandas** y los carga en **SQLite** y archivos **Excel**, junto con un Análisis Exploratorio de Datos (EDA) en Jupyter Notebook.

## Descripción

El proyecto trabaja con tres colecciones de MongoDB:

| Colección | Contenido |
|---|---|
| `Listings` | Anuncios: ubicación, tipo de alojamiento, precio, noches mínimas, disponibilidad, reseñas. |
| `Reviews` | Reseñas de los huéspedes por anuncio (`listing_id`, `date`, `comments`). |
| `Calendar` | Disponibilidad y precio diario de cada anuncio. |

### Objetivos

- Extraer las colecciones de MongoDB y convertirlas en DataFrames.
- Identificar problemas de calidad de datos mediante un EDA (nulos, duplicados, outliers).
- Limpiar y transformar los datos: duplicados, nulos, normalización de precios, fechas y categorización de precios.
- Cargar los datos transformados en una base de datos SQLite (`airbnb_data.db`) y exportarlos a Excel.
- Registrar todo el proceso en un sistema de logs centralizado.

## Estructura del proyecto

```
etl_airbnb/
├── notebooks/
│   └── exploracion_airbnb.ipynb   # Análisis exploratorio (EDA)
├── src/
│   ├── logger.py                  # Logs centralizados (logs/log_YYYYMMDD_HHMM.txt)
│   ├── extraccion.py              # Clase Extraccion (MongoDB -> DataFrame)
│   ├── transformacion.py          # Clase Transformacion (limpieza y enriquecimiento)
│   ├── carga.py                   # Clase Carga (SQLite y Excel)
│   └── main.py                    # Orquestador del pipeline
├── logs/                          # Se crea automáticamente
├── requirements.txt
└── README.md
```

## Requisitos previos

- **Python 3.9+**
- **MongoDB** corriendo localmente (por defecto en `mongodb://localhost:27017/`) con los datos cargados en la base `airbnb` y las colecciones `Listings`, `Reviews` y `Calendar`.

  Ejemplo de carga desde los CSV de Inside Airbnb:

  ```bash
  mongoimport --db airbnb --collection Listings --type csv --headerline --file listings.csv
  mongoimport --db airbnb --collection Reviews  --type csv --headerline --file reviews.csv
  mongoimport --db airbnb --collection Calendar --type csv --headerline --file calendar.csv
  ```

Si tu URI o base de datos son distintas, defínelas con variables de entorno:

```powershell
# Windows (PowerShell)
$env:MONGO_URI = "mongodb://localhost:27017/"
$env:MONGO_DB  = "airbnb"
```

```bash
# Linux / macOS
export MONGO_URI="mongodb://localhost:27017/"
export MONGO_DB="airbnb"
```

## Configuración

1. **Crear el entorno virtual**

   ```bash
   python -m venv venv
   ```

2. **Activar el entorno**

   ```powershell
   # Windows (PowerShell)
   .\venv\Scripts\Activate.ps1
   ```

   ```bash
   # Windows (CMD)
   venv\Scripts\activate.bat

   # Linux / macOS
   source venv/bin/activate
   ```

3. **Instalar dependencias**

   ```bash
   pip install -r requirements.txt
   ```

## Ejecución

### Pipeline ETL

Desde la raíz del proyecto:

```bash
python src/main.py
```

El pipeline:

1. Extrae `Listings` → normaliza `price` a float → limpia nulos y duplicados → crea `categoria_precio` (Económico / Estándar / Premium).
2. Extrae `Reviews` → limpia nulos y duplicados → convierte `date` a `YYYY-MM-DD` y deriva `anio`, `mes`, `dia` y `trimestre`.
3. Carga los resultados en:
   - `airbnb_data.db` (tablas `listings` y `reviews`)
   - `listings_transformado.xlsx` y `reviews_transformado.xlsx` (raíz del proyecto)

Cada ejecución genera un log en `logs/log_YYYYMMDD_HHMM.txt`.

### Análisis exploratorio

```bash
jupyter notebook notebooks/exploracion_airbnb.ipynb
```

### Pruebas automatizadas (QA)

Para ejecutar todas las pruebas automatizadas de calidad de datos con `pytest`:

```bash
pytest -v
```

O usando el ejecutable del entorno virtual:

```bash
python -m pytest -v
```

### Generación del Informe Final en PDF

Para compilar el informe técnico `docs/INFORME_FINAL.md` junto con las gráficas de `docs/img/` en un archivo PDF listo para entrega:

```bash
python src/generador_pdf.py
```

El resultado se generará en la raíz del proyecto como `Informe_Final_ETL.pdf`.

## Tecnologías

- Python, Pandas, PyMongo
- SQLite (`sqlite3`), OpenPyXL
- Matplotlib, Seaborn, Jupyter, Pytest, ReportLab

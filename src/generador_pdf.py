"""
Generador automático del Informe Final en formato PDF.

Parsea el archivo docs/INFORME_FINAL.md e incrusta las imágenes generadas
en docs/img/ para producir un documento 'Informe_Final_ETL.pdf' profesional
con portada, encabezados, tablas y formato ejecutivo.
"""

import os
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
RUTA_MD = RAIZ_PROYECTO / "docs" / "INFORME_FINAL.md"
CARPETA_IMG = RAIZ_PROYECTO / "docs" / "img"
PDF_SALIDA = RAIZ_PROYECTO / "Informe_Final_ETL.pdf"


def limpiar_formato_md(texto: str) -> str:
    """Convierte marcas básicas de Markdown a etiquetas compatibles con ReportLab."""
    # Convertir posibles <br> a <br/> exigido por ReportLab
    texto = re.sub(r"<br\s*/?>", "<br/>", texto, flags=re.IGNORECASE)
    # Negrita (**texto**)
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    # Cursiva (*texto*)
    texto = re.sub(r"\*(.+?)\*", r"<i>\1</i>", texto)
    # Código en línea (`codigo`)
    texto = re.sub(r"`(.+?)`", r'<font face="Courier" color="#b91c1c">\1</font>', texto)
    return texto


class NumeracionPaginaDoc(SimpleDocTemplate):
    """DocTemplate que agrega pie de página dinámico con numeración."""

    def handle_pageEnd(self):
        super().handle_pageEnd()


def agregar_pie_pagina(canvas, doc):
    """Dibuja encabezado sutil y número de página en cada hoja (excepto portada)."""
    if doc.page > 1:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        # Encabezado
        canvas.drawString(
            54, 750, "Inteligencia de Negocios - Informe Técnico ETL Airbnb Bogotá, D.C."
        )
        canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
        canvas.setLineWidth(0.5)
        canvas.line(54, 745, 558, 745)

        # Pie de página
        canvas.drawString(54, 36, "Confidencial / Uso Académico")
        canvas.drawRightString(558, 36, f"Página {doc.page}")
        canvas.line(54, 46, 558, 46)
        canvas.restoreState()


def generar_pdf(ruta_md: Path = RUTA_MD, ruta_pdf: Path = PDF_SALIDA):
    """Lee el Markdown y genera el PDF estilizado."""
    if not ruta_md.exists():
        raise FileNotFoundError(f"No se encontró el archivo de origen: {ruta_md}")

    doc = SimpleDocTemplate(
        str(ruta_pdf),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Estilos tipográficos personalizados
    titulo_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#0f172a"),
        alignment=1,  # Centrado
    )

    subtitulo_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0284c7"),
        alignment=1,
    )

    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#334155"),
        spaceBefore=3,
        spaceAfter=5,
    )

    bullet_style = ParagraphStyle(
        "Bullet_Custom",
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceBefore=2,
        spaceAfter=2,
    )

    code_style = ParagraphStyle(
        "Code_Custom",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0f172a"),
    )

    story = []
    lineas = ruta_md.read_text(encoding="utf-8").splitlines()

    i = 0
    en_codigo = False
    bloque_codigo = []
    en_tabla = False
    filas_tabla = []

    while i < len(lineas):
        linea = lineas[i]

        # Manejo de bloques de código (``` ... ```)
        if linea.strip().startswith("```"):
            if not en_codigo:
                en_codigo = True
                bloque_codigo = []
            else:
                en_codigo = False
                texto_codigo = "\n".join(bloque_codigo)
                # Formatear código en una caja visual
                p_code = Preformatted(texto_codigo, code_style)
                t_code = Table([[p_code]], colWidths=[504])
                t_code.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                            ("PADDING", (0, 0), (-1, -1), 6),
                        ]
                    )
                )
                story.append(Spacer(1, 4))
                story.append(t_code)
                story.append(Spacer(1, 6))
            i += 1
            continue

        if en_codigo:
            bloque_codigo.append(linea)
            i += 1
            continue

        # Detección de tablas Markdown (| col1 | col2 |)
        if "|" in linea and not linea.strip().startswith("#"):
            if not en_tabla:
                en_tabla = True
                filas_tabla = []

            # Si es separador (|---|---|), omitir
            if re.match(r"^\s*\|(?:\s*:?-+:?\s*\|)+\s*$", linea):
                i += 1
                continue

            celdas = [c.strip() for c in linea.strip().split("|")[1:-1]]
            if celdas:
                filas_tabla.append(celdas)
            i += 1
            continue
        elif en_tabla:
            # Fin del bloque de tabla
            en_tabla = False
            if filas_tabla:
                # Construir Table de ReportLab
                data_tabla = []
                for row_idx, fila in enumerate(filas_tabla):
                    fila_pars = []
                    for col in fila:
                        col_limpia = limpiar_formato_md(col)
                        f_style = ParagraphStyle(
                            f"Cell_{row_idx}",
                            parent=body_style,
                            fontSize=8,
                            leading=10,
                            fontName="Helvetica-Bold" if row_idx == 0 else "Helvetica",
                            textColor=colors.white
                            if row_idx == 0
                            else colors.HexColor("#1e293b"),
                        )
                        fila_pars.append(Paragraph(col_limpia, f_style))
                    data_tabla.append(fila_pars)

                t_elem = Table(data_tabla, repeatRows=1)
                t_elem.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0284c7")),
                            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                story.append(Spacer(1, 4))
                story.append(t_elem)
                story.append(Spacer(1, 6))

        # Portada: Título principal
        if linea.startswith("# PROCESO ETL"):
            story.append(Spacer(1, 30))
            story.append(Paragraph(linea.replace("#", "").strip(), titulo_style))
            i += 1
            continue

        if linea.startswith("## INFORME TÉCNICO"):
            story.append(Spacer(1, 8))
            story.append(Paragraph(linea.replace("##", "").strip(), subtitulo_style))
            story.append(Spacer(1, 15))
            story.append(
                HRFlowable(
                    width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceAfter=15
                )
            )
            i += 1
            continue

        # Inserción de imágenes en Markdown (![alt](ruta))
        img_match = re.search(r"!\[(.*?)\]\((.*?)\)", linea)
        if img_match:
            img_rel = img_match.group(2)
            # Buscar la imagen en docs/img o ruta absoluta
            img_path = (RUTA_MD.parent / img_rel).resolve()
            if not img_path.exists():
                img_path = (CARPETA_IMG / Path(img_rel).name).resolve()

            if img_path.exists():
                story.append(Spacer(1, 6))
                # Ajustar ancho a la caja de texto (máx 500 pt)
                img_elem = Image(str(img_path), width=6.8 * inch, height=2.4 * inch)
                story.append(KeepTogether([img_elem, Spacer(1, 4)]))
            else:
                story.append(
                    Paragraph(
                        f"<i>[Imagen pendiente: {img_rel}]</i>",
                        body_style,
                    )
                )
            i += 1
            continue

        # Encabezados
        if linea.startswith("## "):
            texto_h1 = limpiar_formato_md(linea[3:].strip())
            story.append(Spacer(1, 10))
            story.append(Paragraph(texto_h1, h1_style))
            story.append(
                HRFlowable(
                    width="100%", thickness=0.8, color=colors.HexColor("#e2e8f0"), spaceAfter=6
                )
            )
            i += 1
            continue

        if linea.startswith("### "):
            texto_h2 = limpiar_formato_md(linea[4:].strip())
            story.append(Paragraph(texto_h2, h2_style))
            i += 1
            continue

        if linea.startswith("#### "):
            texto_h3 = limpiar_formato_md(linea[5:].strip())
            story.append(
                Paragraph(
                    f"<b>{texto_h3}</b>",
                    ParagraphStyle("H3", parent=body_style, spaceBefore=4, spaceAfter=2),
                )
            )
            i += 1
            continue

        # Separadores horizontales
        if linea.strip() == "---":
            story.append(Spacer(1, 4))
            story.append(
                HRFlowable(
                    width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceAfter=6
                )
            )
            i += 1
            continue

        # Listas con viñetas
        if linea.strip().startswith("- "):
            contenido_viñeta = limpiar_formato_md(linea.strip()[2:])
            story.append(Paragraph(f"• {contenido_viñeta}", bullet_style))
            i += 1
            continue

        # Texto regular
        texto_linea = linea.strip()
        if texto_linea:
            p_limpio = limpiar_formato_md(texto_linea)
            story.append(Paragraph(p_limpio, body_style))
        else:
            story.append(Spacer(1, 3))

        i += 1

    # Construir documento
    doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=agregar_pie_pagina)
    print(f"Informe PDF generado exitosamente en: {ruta_pdf.resolve()}")


if __name__ == "__main__":
    generar_pdf()

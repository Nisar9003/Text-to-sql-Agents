"""
Report Generator module.

Converts a query result (question + SQL + columns + rows) into a
professionally formatted PDF report using reportlab.
"""
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

MAX_ROWS_IN_REPORT = 500  # safety cap so extremely large results don't hang PDF generation


def _make_cell(value, style) -> Paragraph:
    """Wraps a table cell value in a Paragraph so long text wraps instead of overflowing."""
    text = "" if value is None else str(value)
    return Paragraph(escape(text), style)


def generate_report(
    output_path: str,
    question: str,
    sql: str = "",
    columns: list[str] = None,
    rows: list[list] = None,
    mode: str = "sql",
    answer: str = "",
    sources: list[dict] = None,
) -> str:
    """
    Builds a PDF report and writes it to output_path.

    For mode="sql": shows the question, generated SQL, and a results table.
    For mode="document": shows the question, the synthesized answer, and source PDFs used.

    Returns the output_path for convenience.
    """
    columns = columns or []
    rows = rows or []
    sources = sources or []

    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle("cell", parent=styles["Normal"], fontSize=8, leading=10)
    header_style = ParagraphStyle(
        "header", parent=styles["Normal"], fontSize=8, leading=10,
        textColor=colors.white, fontName="Helvetica-Bold",
    )

    # Use landscape orientation for wide tables so columns aren't squeezed
    page_size = landscape(letter) if len(columns) > 5 else letter
    doc = SimpleDocTemplate(
        output_path, pagesize=page_size,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
    )

    story = []

    # --- Title ---
    title = "Text-to-SQL Query Report" if mode == "sql" else "Document Q&A Report"
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 6))
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    story.append(Paragraph(f"Generated: {generated_at}", styles["Normal"]))
    story.append(Spacer(1, 16))

    # --- Question ---
    story.append(Paragraph("Question", styles["Heading2"]))
    story.append(Paragraph(escape(question), styles["Normal"]))
    story.append(Spacer(1, 12))

    if mode == "document":
        # --- Answer ---
        story.append(Paragraph("Answer", styles["Heading2"]))
        story.append(Paragraph(escape(answer).replace("\n", "<br/>"), styles["Normal"]))
        story.append(Spacer(1, 16))

        # --- Sources ---
        if sources:
            story.append(Paragraph("Sources", styles["Heading2"]))
            unique_files = sorted({s["filename"] for s in sources})
            for f in unique_files:
                story.append(Paragraph(f"• {escape(f)}", styles["Normal"]))

        doc.build(story)
        return output_path

    # --- SQL mode: SQL + Results table ---
    story.append(Paragraph("Generated SQL", styles["Heading2"]))
    sql_style = ParagraphStyle(
        "sql", parent=styles["Code"], fontSize=9, leading=12,
        backColor=colors.whitesmoke, borderPadding=6,
    )
    story.append(Paragraph(escape(sql), sql_style))
    story.append(Spacer(1, 16))

    story.append(Paragraph("Results", styles["Heading2"]))

    if not rows:
        story.append(Paragraph("The query returned no rows.", styles["Normal"]))
    else:
        display_rows = rows[:MAX_ROWS_IN_REPORT]

        table_data = [[_make_cell(col, header_style) for col in columns]]
        for row in display_rows:
            table_data.append([_make_cell(cell, cell_style) for cell in row])

        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)

        story.append(Spacer(1, 10))
        footer_text = f"Total rows: {len(rows)}"
        if len(rows) > MAX_ROWS_IN_REPORT:
            footer_text += f" (showing first {MAX_ROWS_IN_REPORT})"
        story.append(Paragraph(footer_text, styles["Normal"]))

    doc.build(story)
    return output_path
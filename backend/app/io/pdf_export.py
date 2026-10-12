"""PDF report built from a stored simulation, not from sample numbers."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.results import SimulationOutput
from app.schemas.spec import ElectionSpecification


def render_pdf(
    spec: ElectionSpecification,
    output: SimulationOutput,
    *,
    created_at: str,
    finished_at: str | None,
) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=letter, title=spec.title[:120])
    styles = getSampleStyleSheet()
    story: list[object] = []
    story.append(Paragraph(escape(spec.title), styles["Title"]))
    story.append(Paragraph(escape(output.disclaimer), styles["BodyText"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Execution metadata", styles["Heading2"]))
    meta = [
        ["Algorithm version", output.algorithm_version],
        ["Specification hash", output.spec_hash],
        ["Seed", str(output.seed)],
        ["Iterations", str(output.iterations)],
        ["Created", created_at],
        ["Finished", finished_at or ""],
        ["Hypothetical", "yes"],
    ]
    story.append(_table(meta))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Assumptions", styles["Heading2"]))
    if spec.assumptions:
        for assumption in spec.assumptions:
            story.append(
                Paragraph(
                    f"<b>{escape(assumption.source)}</b> {escape(assumption.field)}: {escape(assumption.note)}",
                    styles["BodyText"],
                )
            )
    else:
        story.append(Paragraph("No assumption notes were stored.", styles["BodyText"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Methodology", styles["Heading2"]))
    story.append(
        Paragraph(
            escape(
                "Turnout is binomial in eligible voters. Conditional on ballots cast, "
                "valid, blank, and invalid ballots are multinomial. Valid ballots are "
                "allocated by a multinomial preference model, or by ranking blocs for "
                "ranked-choice elections. Means can be fractional expected values in the "
                "analytical section and are labeled separately from simulated draws."
            ),
            styles["BodyText"],
        )
    )
    for scenario in output.scenarios:
        story.append(Spacer(1, 14))
        story.append(Paragraph(escape(f"Scenario: {scenario.scenario_name}"), styles["Heading2"]))
        story.append(
            Paragraph(
                escape(
                    f"Method {scenario.voting_method}. Eligible voters {scenario.eligible_voters}. "
                    f"Mean ballots {scenario.mean_ballots:.2f}. Mean valid {scenario.mean_valid:.2f}. "
                    f"Mean blank {scenario.mean_blank:.2f}. Mean invalid {scenario.mean_invalid:.2f}."
                ),
                styles["BodyText"],
            )
        )
        story.append(Paragraph(escape(scenario.expectation_note), styles["BodyText"]))
        header = ["Candidate", "Mean votes", "Mean share", "Sole-win frequency", "Mean seats"]
        rows = [header]
        chart_values = []
        chart_names = []
        for candidate in scenario.candidates:
            share = "" if candidate.mean_share is None else f"{candidate.mean_share:.4f}"
            seats = "" if candidate.mean_seats is None else f"{candidate.mean_seats:.3f}"
            rows.append(
                [
                    candidate.name,
                    f"{candidate.mean_votes:.2f}",
                    share,
                    f"{candidate.sole_win_frequency:.4f}",
                    seats,
                ]
            )
            chart_names.append(candidate.name[:18])
            chart_values.append(candidate.mean_votes)
        story.append(Spacer(1, 8))
        story.append(_table(rows))
        if any(value > 0 for value in chart_values):
            story.append(Spacer(1, 8))
            story.append(_bar_chart(chart_names, chart_values))
    story.append(Spacer(1, 14))
    story.append(Paragraph("Limitations", styles["Heading2"]))
    for limitation in output.limitations:
        story.append(Paragraph(f"• {escape(limitation)}", styles["BodyText"]))
    document.build(story)
    return buffer.getvalue()


def _table(rows: list[list[str]]) -> Table:
    safe_rows = [[escape(cell) if isinstance(cell, str) else cell for cell in row] for row in rows]
    # Paragraphs would be needed for escaped markup inside Table; plain strings are safer
    # after we already know reportlab Table does not parse XML. Keep raw text, which cannot
    # execute formulas. Escape is unnecessary for Table and would display entities.
    table = Table(rows, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7f0ee")),
                ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8c2b4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    del safe_rows
    return table


def _bar_chart(names: list[str], values: list[float]) -> Drawing:
    drawing = Drawing(460, 180)
    chart = VerticalBarChart()
    chart.x = 40
    chart.y = 30
    chart.height = 130
    chart.width = 400
    chart.data = [values]
    chart.categoryAxis.categoryNames = names
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.bars[0].fillColor = colors.HexColor("#0f6e62")
    drawing.add(chart)
    return drawing

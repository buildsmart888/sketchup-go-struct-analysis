"""Portable result packages used by the Report menu and future batch reporting."""

from __future__ import annotations

import csv
import base64
import html
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
from xml.sax.saxutils import escape

from .units import get_unit_system


@dataclass(frozen=True)
class ReportOptions:
    """Presentation-only controls shared by HTML and PDF report exports."""

    selections: tuple[str, ...]
    include_canvas: bool = True
    include_model_input: bool = True
    include_node_results: bool = True
    include_member_results: bool = True
    figure_scope: str = "selected_full"
    figure_views: tuple[str, ...] = ("Model", "N", "V", "M", "D", "FBD")


def available_report_selections(analysis: Mapping[str, Any]) -> tuple[str, ...]:
    """Return equilibrated result selections suitable for a report section."""

    return tuple(f"case:{name}" for name in analysis.get("cases", {})) + tuple(f"combo:{name}" for name in analysis.get("combos", {}))


def _normalise_options(selection: str | Sequence[str], options: ReportOptions | None) -> ReportOptions:
    selections = (selection,) if isinstance(selection, str) else tuple(selection)
    return options or ReportOptions(selections=selections)


def _selection_result(analysis: Mapping[str, Any], selection: str) -> Mapping[str, Any]:
    if selection.startswith("case:"):
        return analysis.get("cases", {}).get(selection[5:], analysis)
    if selection.startswith("combo:"):
        return analysis.get("combos", {}).get(selection[6:], analysis)
    return analysis


def result_tables(model: Mapping[str, Any], analysis: Mapping[str, Any], selection: str) -> dict[str, list[list[Any]]]:
    result = _selection_result(analysis, selection)
    nodes = [["Node", "X (m)", "Y (m)", "Ux (m)", "Uy (m)", "Rz", "Rx", "Ry", "Mz"]]
    for item in result.get("nodes", []):
        nodes.append([item.get("id"), item.get("x"), item.get("y"), item.get("dx"), item.get("dy"), item.get("rz"), item.get("fx"), item.get("fy"), item.get("mz")])
    members = [["Member", "Node I", "Node J", "Ni", "Vi", "Mi", "Nj", "Vj", "Mj"]]
    for item in result.get("elements", []):
        first, second = item.get("n1_forces", {}), item.get("n2_forces", {})
        members.append([item.get("id"), item.get("n1"), item.get("n2"), first.get("axial"), first.get("shear"), first.get("moment"), second.get("axial"), second.get("shear"), second.get("moment")])
    project = model.get("projectInfo", {})
    summary = [
        ["GO Struct Analysis Report", ""],
        ["Project", project.get("project", "")],
        ["Model", project.get("name", "")],
        ["Selection", selection],
        ["Units", project.get("units", "legacy_kg_m")],
        ["Sign convention", "Solver native sign; display convention is recorded in project settings."],
        ["Nodes", len(result.get("nodes", []))],
        ["Members", len(result.get("elements", []))],
    ]
    return {"Summary": summary, "Nodes": nodes, "Members": members}


def _fixed(value: Any, decimals: int = 4) -> str:
    """Format a report value without altering the raw export tables."""

    return f"{float(value or 0.0):,.{decimals}f}"


def report_result_tables(model: Mapping[str, Any], analysis: Mapping[str, Any], selection: str) -> dict[str, list[list[str]]]:
    """Build the human-readable report tables at the agreed engineering precision.

    Coordinates remain metres. Translational FE displacement is deliberately shown in
    millimetres so the result stays readable even for small deformations.
    """

    result = _selection_result(analysis, selection)
    project = model.get("projectInfo", {})
    units = get_unit_system(project.get("units"))
    force_unit = units.force_unit
    moment_unit = units.moment_label()
    nodes: list[list[str]] = [[
        "Node", "X (m)", "Y (m)", "Ux (mm)", "Uy (mm)", "Rz (rad)",
        f"Rx ({force_unit})", f"Ry ({force_unit})", f"Mz ({moment_unit})",
    ]]
    for item in result.get("nodes", []):
        nodes.append([
            str(item.get("id", "")), _fixed(item.get("x")), _fixed(item.get("y")),
            _fixed(float(item.get("dx", 0.0)) * 1000.0), _fixed(float(item.get("dy", 0.0)) * 1000.0),
            _fixed(item.get("rz"), 6), _fixed(units.force(float(item.get("fx", 0.0)))),
            _fixed(units.force(float(item.get("fy", 0.0)))), _fixed(units.moment(float(item.get("mz", 0.0)))),
        ])
    members: list[list[str]] = [[
        "Member", "Node I", "Node J", f"Ni ({force_unit})", f"Vi ({force_unit})", f"Mi ({moment_unit})",
        f"Nj ({force_unit})", f"Vj ({force_unit})", f"Mj ({moment_unit})",
    ]]
    for item in result.get("elements", []):
        first, second = item.get("n1_forces", {}), item.get("n2_forces", {})
        members.append([
            str(item.get("id", "")), str(item.get("n1", "")), str(item.get("n2", "")),
            _fixed(units.force(float(first.get("axial", 0.0)))), _fixed(units.force(float(first.get("shear", 0.0)))),
            _fixed(units.moment(float(first.get("moment", 0.0)))), _fixed(units.force(float(second.get("axial", 0.0)))),
            _fixed(units.force(float(second.get("shear", 0.0)))), _fixed(units.moment(float(second.get("moment", 0.0)))),
        ])
    summary = [
        ["GO Struct Analysis Report", ""], ["Project", str(project.get("project", ""))],
        ["Model", str(project.get("name", ""))], ["Selection", selection],
        ["Force unit", force_unit], ["Moment unit", moment_unit],
        ["Geometry / stations", "m, 4 decimals"], ["Translations", "mm, 4 decimals"],
        ["Sign convention", "Native solver signs; graph orientation is visual only."],
        ["Nodes", str(len(result.get("nodes", [])))], ["Members", str(len(result.get("elements", [])))],
    ]
    return {"Summary": summary, "Nodes": nodes, "Members": members}


def model_input_tables(model: Mapping[str, Any]) -> dict[str, list[list[Any]]]:
    """Engineering input schedules, intentionally separate from calculated result tables."""

    nodes = [["Node", "X (m)", "Y (m)", "Support"]]
    nodes.extend([[node.get("id"), node.get("x"), node.get("y"), node.get("support", "Free")] for node in model.get("nodes", [])])
    members = [["Member", "Node I", "Node J", "Section", "Type", "Release"]]
    members.extend(
        [[member.get("id"), member.get("n1"), member.get("n2"), member.get("sec"), member.get("memberType", "Frame"), member.get("release", "Rigid-Rigid")]
        for member in model.get("elements", [])]
    )
    sections = [["Section", "Name", "E", "A", "I", "Density"]]
    sections.extend([[section.get("id"), section.get("name", ""), section.get("e"), section.get("a"), section.get("i"), section.get("density")] for section in model.get("sections", [])])
    nodal_loads = [["Case", "Node", "Fx", "Fy", "Mz"]]
    nodal_loads.extend([[load.get("lcase"), load.get("node"), load.get("fx", 0.0), load.get("fy", 0.0), load.get("mz", 0.0)] for load in model.get("nloads", [])])
    member_loads = [["Case", "Member", "Type", "Direction", "w1 / P", "w2 / M", "At x (m)"]]
    member_loads.extend(
        [[load.get("lcase"), load.get("elem"), load.get("type", "Distributed"), load.get("dir", "Local Y"), load.get("w1", load.get("p", "")), load.get("w2", load.get("m", "")), load.get("x_m", "")]
        for load in model.get("eloads", [])]
    )
    combinations = [["Combination", "Load case factors"]]
    combinations.extend([[combo.get("name"), ", ".join(f"{name} = {factor:g}" for name, factor in combo.get("factors", {}).items())] for combo in model.get("loadcombos", [])])
    return {"Node Schedule": nodes, "Member Schedule": members, "Section Schedule": sections, "Nodal Loads": nodal_loads, "Member Loads": member_loads, "Load Combinations": combinations}


def truss_axial_extrema(
    model: Mapping[str, Any],
    analysis: Mapping[str, Any],
    selection: str,
    *,
    formatted: bool = False,
) -> list[list[Any]]:
    """Return governing tension/compression rows for pure Truss and Hybrid Truss members."""

    truss_ids = {
        int(member["id"])
        for member in model.get("elements", [])
        if str(member.get("memberType", "Truss" if str(model.get("projectInfo", {}).get("analysisType", "")).lower() in {"truss", "2d truss"} else "Frame")) == "Truss"
    }
    if not truss_ids:
        return []
    values = []
    for member in _selection_result(analysis, selection).get("elements", []):
        if int(member.get("id", -1)) not in truss_ids:
            continue
        values.append((float(member.get("n1_forces", {}).get("axial", 0.0)), member))
    tension = max((item for item in values if item[0] > 1.0e-12), default=None, key=lambda item: item[0])
    compression = min((item for item in values if item[0] < -1.0e-12), default=None, key=lambda item: item[0])
    units = get_unit_system(model.get("projectInfo", {}).get("units"))
    rows = [["State", "Member", "Node I", "Node J", f"Axial N ({units.force_unit if formatted else 'solver units'})"]]
    if tension is not None:
        value, member = tension
        rows.append(["Maximum tension (+N)", member.get("id"), member.get("n1"), member.get("n2"), _fixed(units.force(value)) if formatted else value])
    if compression is not None:
        value, member = compression
        rows.append(["Maximum compression (-N)", member.get("id"), member.get("n1"), member.get("n2"), _fixed(units.force(value)) if formatted else value])
    return rows if len(rows) > 1 else []


def write_csv_bundle(directory: Path, model: Mapping[str, Any], analysis: Mapping[str, Any], selection: str) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    # CSV is a user-facing result schedule, so it intentionally matches the PDF/HTML
    # labels, display units, and precision rather than exposing solver-native fields.
    for name, rows in report_result_tables(model, analysis, selection).items():
        path = directory / f"{name.lower()}.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as stream:
            csv.writer(stream).writerows(rows)
        written.append(path)
    return written


def write_xlsx(path: Path, model: Mapping[str, Any], analysis: Mapping[str, Any], selection: str) -> None:
    """Write a small dependency-free XLSX workbook with one sheet per result table."""
    # Keep every portable report format aligned with the same engineering schedule.
    tables = report_result_tables(model, analysis, selection)
    sheet_names = list(tables)

    def column(index: int) -> str:
        name = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            name = chr(65 + remainder) + name
        return name

    def cell(reference: str, value: Any) -> str:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f'<c r="{reference}"><v>{value}</v></c>'
        return f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value if value is not None else ""))}</t></is></c>'

    sheets: list[str] = []
    for rows in tables.values():
        lines = []
        for row_number, row in enumerate(rows, start=1):
            cells = "".join(cell(f"{column(index)}{row_number}", value) for index, value in enumerate(row, start=1))
            lines.append(f'<row r="{row_number}">{cells}</row>')
        sheets.append('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(lines) + "</sheetData></worksheet>")
    workbook_sheets = "".join(f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>' for index, name in enumerate(sheet_names, start=1))
    content_types = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>']
    for index in range(1, len(sheets) + 1):
        content_types.append(f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    content_types.append("</Types>")
    relationships = "".join(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>' for index in range(1, len(sheets) + 1))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "".join(content_types))
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + workbook_sheets + "</sheets></workbook>")
        archive.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + relationships + "</Relationships>")
        for index, sheet in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", sheet)


def _html_table(name: str, rows: list[list[Any]]) -> str:
    table = "".join(
        "<tr>" + "".join(f"<{'th' if row_index == 0 else 'td'}>{html.escape(str(value if value is not None else ''))}</{'th' if row_index == 0 else 'td'}>" for value in row) + "</tr>"
        for row_index, row in enumerate(rows)
    )
    return f"<h2>{html.escape(name)}</h2><table>{table}</table>"


def _canvas_data_uri(image: str | bytes | None) -> str | None:
    if image is None:
        return None
    if isinstance(image, str):
        return image if image.startswith("data:image/") else f"data:image/png;base64,{image}"
    return f"data:image/png;base64,{base64.b64encode(image).decode('ascii')}"


def _canvas_figures(images: Mapping[str, str | bytes] | str | bytes | None, selection: str) -> str:
    """Render separately captioned report figures, retaining legacy one-image input."""

    if images is None:
        return ""
    image_set: Mapping[str, str | bytes] = images if isinstance(images, Mapping) else {"Canvas": images}
    figures = []
    for label, image in image_set.items():
        uri = _canvas_data_uri(image)
        if uri:
            safe_label = html.escape(str(label))
            figures.append(
                f"<figure class='canvas-figure'><img src='{html.escape(uri, quote=True)}' "
                f"alt='{safe_label} canvas view for {html.escape(selection)}'>"
                f"<figcaption>{safe_label} view: {html.escape(selection)}</figcaption></figure>"
            )
    return "<div class='canvas-views'>" + "".join(figures) + "</div>" if figures else ""


def build_html_report(
    model: Mapping[str, Any],
    analysis: Mapping[str, Any],
    selection: str | Sequence[str],
    *,
    options: ReportOptions | None = None,
    canvas_images: Mapping[str, Mapping[str, str | bytes] | str | bytes] | None = None,
) -> str:
    """Create a self-contained engineering report with optional canvas snapshots."""

    resolved = _normalise_options(selection, options)
    sections = []
    project = model.get("projectInfo", {})
    project_rows = [
        ["Project", project.get("project", "")],
        ["Model", project.get("name", "")],
        ["Engineer", project.get("engineer", "")],
        ["Location", project.get("location", "")],
        ["Units", project.get("units", "legacy_kg_m")],
        ["Sign convention", "Native solver signs; graph orientation affects drawing placement only."],
    ]
    sections.append(_html_table("Project Information", project_rows))
    if resolved.include_model_input:
        sections.extend(_html_table(name, rows) for name, rows in model_input_tables(model).items())
    attached_canvas_selections: set[str] = set()
    for result_selection in resolved.selections:
        result_sections = [
            _html_table(name, rows)
            for name, rows in report_result_tables(model, analysis, result_selection).items()
            if (name != "Nodes" or resolved.include_node_results) and (name != "Members" or resolved.include_member_results)
        ]
        extrema = truss_axial_extrema(model, analysis, result_selection, formatted=True)
        if extrema:
            result_sections.append(_html_table("Truss Axial Extremes", extrema))
        canvas = _canvas_figures((canvas_images or {}).get(result_selection), result_selection) if resolved.include_canvas else ""
        if canvas:
            attached_canvas_selections.add(result_selection)
        sections.append(f"<section class='result-section'><h1>Results: {html.escape(result_selection)}</h1>{canvas}{''.join(result_sections)}</section>")
    # A report can contain full tables for several cases while intentionally showing
    # figures for the result currently visible on the canvas, including Envelope.
    for figure_selection, figures in (canvas_images or {}).items():
        if figure_selection in attached_canvas_selections:
            continue
        canvas = _canvas_figures(figures, figure_selection) if resolved.include_canvas else ""
        if canvas:
            sections.append(f"<section class='result-section'><h1>Canvas views: {html.escape(figure_selection)}</h1>{canvas}</section>")
    return "<!doctype html><html><head><meta charset='utf-8'><title>GO Struct Report</title><style>@page{size:A4;margin:14mm}body{font-family:Segoe UI,Arial;margin:0;color:#172033;font-size:9pt}h1{color:#0f766e;border-bottom:2px solid #0f766e;padding-bottom:4px}h2{color:#164e63;margin:16px 0 6px;font-size:12pt}table{border-collapse:collapse;width:100%;table-layout:fixed;margin:8px 0 18px;page-break-inside:avoid;break-inside:avoid}td,th{border:1px solid #cbd5e1;padding:4px;text-align:left;overflow-wrap:anywhere;word-wrap:break-word}th{background:#e2e8f0}.canvas-views{margin:10px 0 18px}.canvas-figure{width:460px;max-width:100%;margin:0 0 12px;page-break-inside:avoid;break-inside:avoid}.canvas-figure img{display:block;width:460px;max-width:100%;height:auto;border:1px solid #cbd5e1}.canvas-figure figcaption{color:#475569;font-size:8.5pt;margin-top:4px}.result-section{page-break-before:always;break-before:page}</style></head><body><h1>GO Struct Analysis Report</h1>" + "".join(sections) + "</body></html>"


def write_html_report(
    path: Path,
    model: Mapping[str, Any],
    analysis: Mapping[str, Any],
    selection: str | Sequence[str],
    *,
    options: ReportOptions | None = None,
    canvas_images: Mapping[str, Mapping[str, str | bytes] | str | bytes] | None = None,
) -> None:
    path.write_text(build_html_report(model, analysis, selection, options=options, canvas_images=canvas_images), encoding="utf-8")

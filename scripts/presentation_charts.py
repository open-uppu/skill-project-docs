"""Evidence-backed HTML charts for Markdown and self-contained presentations.

Pure standard-library rendering; source JSON remains the owner of every value.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
import chart_families
import html_shapes as shapes

PALETTE = ["#17665c", "#4366a0", "#9c5c16", "#8561a6", "#b04e54", "#497c85"]
CHOICES = {"comparison": "bar", "trend": "line", "relationship": "scatter", "composition": "stacked-bar", "matrix": "heatmap"}
RATIONALE = {
    "bar": "Aligned bars make category magnitudes easy to compare; the value axis includes zero.",
    "line": "Connected observations show change over ordered numeric or date values; gaps must be explicit in the source.",
    "scatter": "Point positions show association between two numeric measures; association does not establish causation.",
    "stacked-bar": "Segments show absolute contributions to a total; middle segments are harder to compare across groups.",
    "heatmap": "Cell color reveals patterns across two categories; use the values and table for exact comparisons.",
    "custom": "A project-specific rendering is used because the standard chart types do not answer this question clearly.",
}
RATIONALE.update(chart_families.RATIONALE)
CHOICES.update(chart_families.INTENTS)


def escape(value):
    return html.escape(str(value), quote=True)


def html_visual(visual):
    return '<p class="chart-overflow-hint">Scroll horizontally when needed; exact values are in the source table.</p><div class="chart-visual" tabindex="0" aria-label="Scrollable chart; source values follow">'+visual+'</div>'


def inside(root, value):
    path = (Path(root) / value).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError("presentation source or asset must remain inside the project")
    return path


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("chart values must be finite numbers; missing values are not zero")
    return float(value)


def fmt(value):
    return f"{value:,.4g}" if isinstance(value, (int, float)) else str(value)


def source_rows(root, spec):
    source = spec["source"]
    path = inside(root, source["path"])
    raw = path.read_bytes()
    data = json.loads(raw)
    pointer = source.get("pointer", "")
    if pointer and not pointer.startswith("/"):
        raise ValueError("source pointer must be an RFC 6901 JSON pointer")
    for part in pointer.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        data = data[int(part)] if isinstance(data, list) else data[part]
    if not isinstance(data, list) or not data or not all(isinstance(row, dict) for row in data):
        raise ValueError("chart source must select a nonempty array of row objects")
    return data, hashlib.sha256(raw).hexdigest()


html_text = shapes.text


def selected_type(spec):
    typ = spec.get("type", "auto")
    if typ == "auto":
        if spec.get("intent") not in CHOICES:
            raise ValueError("auto chart needs a supported intent: " + ", ".join(sorted(CHOICES)))
        typ = CHOICES[spec["intent"]]
    if typ not in RATIONALE:
        raise ValueError("unknown chart type")
    return typ


def custom_html(root, spec, checksum):
    if not spec.get("reason"):
        raise ValueError("custom chart requires a reason for the custom encoding")
    asset = inside(root, spec["asset"])
    generator = inside(root, spec["generator"])
    if asset.suffix.lower() not in {'.html', '.htm'}:
        raise ValueError('custom chart asset must be HTML')
    if not generator.is_file():
        raise ValueError("custom chart generator does not exist")
    raw = asset.read_text(encoding="utf-8")
    from ado_html_report import validate_html
    validate_html(raw.encode('utf-8'))
    def metadata(name):
        match = re.search(r'<meta\s+name=["\']'+re.escape(name)+r'["\']\s+content=["\']([0-9a-f]{64})["\']\s*/?>',raw,re.I)
        return match.group(1) if match else None
    if metadata('project-docs-source-sha256') != checksum:
        raise ValueError("custom chart source checksum is stale or missing")
    if metadata('project-docs-generator-sha256') != hashlib.sha256(generator.read_bytes()).hexdigest():
        raise ValueError("custom chart generator checksum is stale or missing")
    body = re.search(r'<body\b[^>]*>(.*?)</body\s*>',raw,re.I|re.S)
    if not body: raise ValueError('custom HTML needs a body')
    return '<div role="img" aria-label="'+escape(spec['title'])+'">'+body.group(1)+'</div>'


def render(root, spec):
    for key in ("id", "title", "question", "source", "limitations", "unit"):
        if key not in spec or spec[key] is None or (key != "unit" and not spec[key]):
            raise ValueError("chart requires " + key)
    if not re.fullmatch(r"[a-z][a-z0-9-]*", spec["id"]):
        raise ValueError("chart id must be a lower-case slug")
    if not isinstance(spec["unit"],str): raise ValueError("chart unit must be text (empty for dimensionless data)")
    rows, checksum = source_rows(root, spec)
    typ = selected_type(spec)
    color = spec.get("color", PALETTE[0])
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("chart color must be a six-digit hex color")
    if typ in chart_families.RATIONALE:
        visual,fields,table = chart_families.render(typ,rows,spec)
        return package(spec,typ,visual,fields,table,checksum)
    x, y = spec.get("x"), spec.get("y")
    series = spec.get("series", [])
    if series and typ != "stacked-bar": raise ValueError("series are supported by stacked-bar; use a custom chart for grouped/multiple-series views")
    if len({s["field"] for s in series}) != len(series): raise ValueError("series fields must be unique")
    fields = [x, *[s["field"] for s in series]] if typ == "stacked-bar" else [x, y]
    if typ == "heatmap":
        fields.append(spec.get("value"))
    if typ == "custom":
        fields = spec.get("fields", list(rows[0]))
    if not fields or any(not f for f in fields) or any(f not in row for row in rows for f in fields):
        raise ValueError("every source row must contain the selected chart fields")
    table = [[row[f] for f in fields] for row in rows]
    parts = []
    left, right, top, bottom = 80, 918, 55, 365
    if typ == "custom":
        visual = custom_html(root, spec, checksum)
    elif typ in {"bar", "stacked-bar"}:
        if len({str(row[x]) for row in rows}) != len(rows):
            raise ValueError("bar categories must be unique; aggregate explicitly in the source")
        if len(rows) > 16:
            raise ValueError("more than 16 bar categories: split the question or use a custom chart")
        if typ == "stacked-bar" and not 1 <= len(series) <= 6:
            raise ValueError("stacked bars require 1–6 named series")
        left, right = 240, 865
        bottom = top + max(36,min(60,280/len(rows)))*len(rows)
        height = bottom+95
        parts.append(html_text(24,25,spec.get("x_label",x),15))
        values = [[number(row[s["field"]]) for s in series] if series else [number(row[y])] for row in rows]
        if typ == "stacked-bar" and any(v < 0 for group in values for v in group):
            raise ValueError("stacked parts cannot be negative")
        totals = [sum(group) for group in values]
        lo, hi = min(0, min(totals)), max(0, max(totals))
        if lo == hi: hi = lo+1
        scale = lambda v: left+(v-lo)/(hi-lo)*(right-left)
        for tick in range(5):
            v = lo+(hi-lo)*tick/4; px = scale(v)
            parts.append(shapes.line(px,top,px,bottom,'#dce4e4'))
            parts.append(html_text(px, bottom+25, fmt(v), anchor="middle"))
        gap = (bottom-top)/len(rows)
        for i, (row, group) in enumerate(zip(rows, values)):
            py = top+gap*(i+.5)
            label = str(row[x])
            lines = textwrap.wrap(label, 25)[:2] or [""]
            for j, line in enumerate(lines):
                parts.append(html_text(left-18, py+5+(j-(len(lines)-1)/2)*16, line, 14, "end"))
            current = 0
            for n, val in enumerate(group):
                px, end = scale(current), scale(current+val)
                fill = PALETTE[n] if series else color
                parts.append(shapes.rect(min(px,end),py-min(gap*.55,30)/2,abs(end-px),min(gap*.55,30),fill,f'{label}: {fmt(val)}'))
                current += val
            parts.append(html_text(935, py+5, fmt(current), 13, "end"))
        parts.append(html_text((left+right)/2, height-20, spec.get("y_label", y or "Total")+ (" ("+spec["unit"]+")" if spec["unit"] else ""), 15, "middle"))
        if series:
            for n, entry in enumerate(series):
                parts.append(html_text(80+n*145, 25, entry.get("label", entry["field"]), 13, fill=PALETTE[n]))
        visual = shapes.chart(spec['title'],spec['question'],parts,height)
    elif typ in {"line", "scatter"}:
        if len(rows) > 1000:
            raise ValueError("more than 1000 points: aggregate explicitly or use a custom chart")
        def xpos(value):
            if isinstance(value, (int, float)) and not isinstance(value, bool): return number(value)
            if typ != "line": raise ValueError("scatter x values must be numeric")
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).timestamp()
        xs, ys = [xpos(row[x]) for row in rows], [number(row[y]) for row in rows]
        if typ == "line" and (len(rows) < 2 or any(a >= b for a, b in zip(xs, xs[1:]))):
            raise ValueError("line charts need at least two strictly increasing x values; never connect unordered categories")
        xmin, xmax = min(xs), max(xs); ymin, ymax = min(ys), max(ys)
        if xmin == xmax: xmin -= .5; xmax += .5
        if ymin == ymax: ymin -= .5; ymax += .5
        sx = lambda v: left+(v-xmin)/(xmax-xmin)*(right-left)
        sy = lambda v: bottom-(v-ymin)/(ymax-ymin)*(bottom-top)
        for tick in range(5):
            v = ymin+(ymax-ymin)*tick/4; py = sy(v)
            parts.append(shapes.line(left,py,right,py,'#dce4e4'))
            parts.append(html_text(left-12, py+5, fmt(v), anchor="end"))
        indexes = sorted({round(i*(len(rows)-1)/4) for i in range(5)})
        for i in indexes:
            label = fmt(rows[i][x])
            if isinstance(rows[i][x],str):
                same_day = len({str(row[x])[:10] for row in rows}) == 1
                label = str(rows[i][x])[11:19] if same_day and "T" in str(rows[i][x]) else str(rows[i][x])[:10]
            parts.append(html_text(sx(xs[i]), bottom+28, label, 12, "middle"))
        if typ == "line":
            parts.append(shapes.polyline([(sx(a),sy(b)) for a,b in zip(xs,ys)],color))
        for row, a, b in zip(rows, xs, ys):
            parts.append(shapes.dot(sx(a),sy(b),5,color,f'{row[x]}: {fmt(b)}'))
        parts.append(html_text(left, 25, spec.get("y_label", y)+(" ("+spec["unit"]+")" if spec["unit"] else ""), 15))
        parts.append(html_text((left+right)/2, 430, spec.get("x_label", x), 15, "middle"))
        visual = shapes.chart(spec['title'],spec['question'],parts,460)
    else:
        xs, ys = list(dict.fromkeys(str(row[x]) for row in rows)), list(dict.fromkeys(str(row[y]) for row in rows))
        if len(xs) > 12 or len(ys) > 12:
            raise ValueError("heatmap limited to 12 x 12 cells; aggregate explicitly or use a custom chart")
        cells = {(str(row[x]), str(row[y])): number(row[spec["value"]]) for row in rows}
        if len(cells) != len(rows): raise ValueError("duplicate heatmap cells; aggregate in the source first")
        low, high = min(cells.values()), max(cells.values())
        left = 180
        cw, ch = (right-left)/len(xs), (bottom-top)/len(ys)
        for i, label in enumerate(xs): parts.append(html_text(left+cw*(i+.5), bottom+25, label, 12, "middle"))
        for j, label in enumerate(ys): parts.append(html_text(left-15, top+ch*(j+.5)+5, label, 13, "end"))
        for j, yy in enumerate(ys):
            for i, xx in enumerate(xs):
                val = cells.get((xx, yy))
                strength = (val-low)/(high-low) if val is not None and high != low else .5
                rgb=(int(237-214*strength),int(245-143*strength),int(242-150*strength))
                fill = f"rgb({rgb[0]},{rgb[1]},{rgb[2]})" if val is not None else "#edf0f0"
                linear=[v/255/12.92 if v/255<=.04045 else ((v/255+.055)/1.055)**2.4 for v in rgb]
                luminance=sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))
                foreground='#ffffff' if 1.05/(luminance+.05)>=(luminance+.05)/.05 else '#000000'
                parts.append(shapes.rect(left+i*cw,top+j*ch,cw-3,ch-3,fill))
                parts.append(html_text(left+cw*(i+.5), top+ch*(j+.5)+5, fmt(val) if val is not None else "No data", 14, "middle", foreground if val is not None else "#273d45"))
        parts.append(html_text(left, 420, f"Color scale: {fmt(low)} to {fmt(high)} {spec['unit']}. Missing cells are not zero.", 14))
        visual = shapes.chart(spec['title'],spec['question'],parts,460)
    return package(spec,typ,visual,fields,table,checksum)


def package(spec,typ,visual,fields,table,checksum):
    notes = spec.get("annotations", [])
    if not isinstance(notes, list) or not all(isinstance(note, str) for note in notes):
        raise ValueError("annotations must be a list of evidence-backed text notes")
    return {"id": spec["id"], "title": spec["title"], "question": spec["question"], "type": typ,
            "html": visual, "fields": fields, "rows": table, "source": spec["source"], "sha256": checksum,
            "why": spec.get("reason", RATIONALE[typ]), "limits": spec["limitations"],
            "takeaway": spec.get("takeaway", ""), "annotations": notes}

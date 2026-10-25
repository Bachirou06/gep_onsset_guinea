"""HTML rendering: tables from frames (never emitting nan) and the jinja2 page."""
import html as _html
import math
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES = Path(__file__).resolve().parent / "templates"
NA = "n/a"


def fmt_cell(value, spec: str | None) -> str:
    """Format one cell; NaN, None and empty become 'n/a'."""
    if value is None:
        return NA
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return NA
    if isinstance(value, str):
        return _html.escape(value) if value.strip() else NA
    if spec:
        try:
            return spec.format(value)
        except (ValueError, TypeError):
            return _html.escape(str(value))
    if isinstance(value, (int,)) or (hasattr(value, "is_integer") and float(value).is_integer() and abs(value) >= 1000):
        return f"{int(round(value)):,}"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return _html.escape(str(value))


def table_html(df: pd.DataFrame, formats: dict | None = None, index: bool = True, caption: str | None = None,
               css_class: str = "data", index_label: str = "", col_labels: dict | None = None,
               table_id: str | None = None, total_rows=None) -> str:
    """A compact HTML table. formats maps column name to a format string ('{:,.0f}');
    col_labels maps column name to a display label; total_rows lists the index labels
    rendered as totals (bold), nothing else is."""
    formats = formats or {}
    col_labels = col_labels or {}
    total_rows = set(total_rows or [])
    cols = list(df.columns)
    parts = [f'<table class="{css_class}"' + (f' id="{table_id}"' if table_id else "") + ">"]
    if caption:
        parts.append(f"<caption>{_html.escape(caption)}</caption>")
    parts.append("<thead><tr>")
    if index:
        parts.append(f"<th>{_html.escape(index_label)}</th>")
    for c in cols:
        parts.append(f"<th>{_html.escape(str(col_labels.get(c, c)))}</th>")
    parts.append("</tr></thead><tbody>")
    for idx, row in df.iterrows():
        key = idx if not isinstance(idx, tuple) else idx[-1]
        parts.append('<tr class="total">' if key in total_rows else "<tr>")
        if index:
            parts.append(f"<th>{fmt_cell(idx if not isinstance(idx, tuple) else ' / '.join(map(str, idx)), None)}</th>")
        for c in cols:
            v = row[c]
            cls = ' class="num"' if isinstance(v, (int, float)) and not isinstance(v, bool) else ""
            parts.append(f"<td{cls}>{fmt_cell(v, formats.get(c))}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def render(context: dict, template_name: str = "report.html.j2") -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=False, undefined=StrictUndefined,
                      trim_blocks=True, lstrip_blocks=True)
    env.filters["e"] = lambda s: _html.escape(str(s))
    context = dict(context)
    context["css"] = (TEMPLATES / "style.css").read_text(encoding="utf-8")
    return env.get_template(template_name).render(**context)

"""Plotly chart builders. Every function returns a plotly.graph_objects.Figure; fig_to_div
turns it into an HTML fragment without the plotly.js bundle, which the page includes once."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from report.constants import (ACCENT, CASE_COLOUR, CASE_STUDY_NAME, COST_LEVELS, REFERENCE_COST,
                              SENSITIVITY_CASES, SERVED_CODES, TECH_COLOUR, TECH_LABEL, TECH_ORDER, YEARS)

FONT = dict(family="Segoe UI, Helvetica, Arial, sans-serif", size=13, color="#222222")
LAYOUT = dict(template="simple_white", font=FONT, margin=dict(l=60, r=30, t=70, b=60),
              legend=dict(orientation="h", yanchor="bottom", y=-0.28, xanchor="left", x=0),
              hoverlabel=dict(font=dict(family=FONT["family"])))


def _case_label(case: str) -> str:
    name = CASE_STUDY_NAME.get(case, case)
    return name if name == case else f"{name}"


def _apply(fig: go.Figure, title: str, height: int = 460) -> go.Figure:
    fig.update_layout(title=dict(text=title, x=0, xanchor="left", font=dict(size=16)), height=height, **LAYOUT)
    return fig


def stacked_by_tech(long_df: pd.DataFrame, value_col: str, title: str, y_title: str, x_order: list,
                    years=YEARS, code_col: str = "code", x_col: str = "demand_case") -> go.Figure:
    """Two panels (2030 | 2040), x = demand case, one stacked bar trace per technology."""
    fig = make_subplots(rows=1, cols=len(years), subplot_titles=[str(y) for y in years], shared_yaxes=True,
                        horizontal_spacing=0.06)
    codes = [c for c in TECH_ORDER if (long_df[code_col] == c).any()]
    for j, year in enumerate(years, start=1):
        sub = long_df[long_df["year"] == year]
        for c in codes:
            s = sub[sub[code_col] == c].set_index(x_col)[value_col].reindex(x_order).fillna(0.0)
            fig.add_trace(go.Bar(x=[_case_label(k) for k in x_order], y=s.to_numpy(), name=TECH_LABEL[c],
                                 marker_color=TECH_COLOUR[c], legendgroup=TECH_LABEL[c], showlegend=(j == 1),
                                 hovertemplate=f"{TECH_LABEL[c]}<br>%{{x}}: %{{y:,.0f}}<extra></extra>"),
                          row=1, col=j)
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title_text=y_title, row=1, col=1, tickformat=",.0f")
    return _apply(fig, title, height=480)


def grouped_metric_bars(df: pd.DataFrame, metric_cols: list, titles: list, case_order: list,
                        case_col: str = "demand_case", title: str = "") -> go.Figure:
    """Small multiples: one panel per metric, one bar per demand case."""
    fig = make_subplots(rows=1, cols=len(metric_cols), subplot_titles=titles, horizontal_spacing=0.08)
    d = df.set_index(case_col).reindex(case_order)
    for j, col in enumerate(metric_cols, start=1):
        fig.add_trace(go.Bar(x=[_case_label(k) for k in case_order], y=d[col].to_numpy(),
                             marker_color=[CASE_COLOUR.get(k, ACCENT) for k in case_order], showlegend=False,
                             hovertemplate="%{x}: %{y:,.2f}<extra></extra>"), row=1, col=j)
    return _apply(fig, title, height=420)


def lines_vs_cost(sens_df: pd.DataFrame, y_col: str, y_title: str, cases=SENSITIVITY_CASES,
                  title: str = "") -> go.Figure:
    """One line per demand case over the grid-cost levels, reference cost marked."""
    fig = go.Figure()
    for case in cases:
        s = sens_df[sens_df["demand_case"] == case].sort_values("grid_cost")
        fig.add_trace(go.Scatter(x=s["grid_cost"].tolist(), y=s[y_col].tolist(), mode="lines+markers",
                                 name=_case_label(case), line=dict(color=CASE_COLOUR.get(case, ACCENT), width=2.5),
                                 marker=dict(size=9),
                                 hovertemplate=f"{_case_label(case)}<br>%{{x}} USD/kWh: %{{y:,.2f}}<extra></extra>"))
    fig.add_vline(x=REFERENCE_COST, line=dict(color="#888888", dash="dash", width=1.2))
    fig.add_annotation(x=REFERENCE_COST, y=1.02, yref="paper", text="reference", showarrow=False,
                       font=dict(size=11, color="#666666"), xanchor="left")
    fig.update_xaxes(title_text="Grid generation cost (USD/kWh)", tickvals=COST_LEVELS, tickformat=".3f")
    fig.update_yaxes(title_text=y_title, tickformat=",.0f" if "USD/kWh" not in y_title else ".3f", rangemode="tozero")
    return _apply(fig, title or y_title, height=440)


def shares_vs_cost(long_df: pd.DataFrame, cases: list, title: str = "") -> go.Figure:
    """Stacked population shares (percent) by technology against the grid cost, one panel per case.
    long_df columns: demand_case, grid_cost, code, population."""
    fig = make_subplots(rows=1, cols=len(cases), subplot_titles=[_case_label(c) for c in cases],
                        shared_yaxes=True, horizontal_spacing=0.05)
    for j, case in enumerate(cases, start=1):
        sub = long_df[long_df["demand_case"] == case]
        tot = sub.groupby("grid_cost")["population"].sum()
        costs = sorted(tot.index)
        for c in [k for k in TECH_ORDER if k in SERVED_CODES]:
            pop = sub[sub["code"] == c].set_index("grid_cost")["population"].reindex(costs).fillna(0.0)
            share = (pop / tot.reindex(costs) * 100).to_numpy()
            fig.add_trace(go.Bar(x=[f"{g}" for g in costs], y=share, name=TECH_LABEL[c], marker_color=TECH_COLOUR[c],
                                 legendgroup=TECH_LABEL[c], showlegend=(j == 1),
                                 hovertemplate=f"{TECH_LABEL[c]}<br>%{{x}} USD/kWh: %{{y:.1f}}%<extra></extra>"),
                          row=1, col=j)
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title_text="Share of 2040 population (%)", row=1, col=1, range=[0, 100])
    fig.update_xaxes(title_text="Grid cost (USD/kWh)")
    return _apply(fig, title, height=460)


def lcoe_histograms(hist_long: pd.DataFrame, title: str = "") -> go.Figure:
    """Population-weighted LCOE distributions, one step line per demand case.
    hist_long columns: demand_case, bin_left, people."""
    fig = go.Figure()
    for case, sub in hist_long.groupby("demand_case", sort=False):
        sub = sub.sort_values("bin_left")
        fig.add_trace(go.Scatter(x=sub["bin_left"], y=sub["people"], mode="lines", line_shape="hv",
                                 name=_case_label(case), line=dict(color=CASE_COLOUR.get(case, ACCENT), width=2),
                                 hovertemplate=f"{_case_label(case)}<br>%{{x:.3f}} USD/kWh: %{{y:,.0f}} people<extra></extra>"))
    fig.update_xaxes(title_text="Delivered LCOE (USD/kWh)", tickformat=".2f")
    fig.update_yaxes(title_text="People (2040)", tickformat=",.0f")
    return _apply(fig, title, height=420)


def switch_matrix(flows: pd.DataFrame, title: str) -> go.Figure:
    """Heatmap of people moving from one technology (rows) to another (columns)."""
    codes = [c for c in TECH_ORDER if c in set(flows["from_code"]) | set(flows["to_code"])]
    z = np.zeros((len(codes), len(codes)))
    for _, r in flows.iterrows():
        z[codes.index(int(r["from_code"])), codes.index(int(r["to_code"]))] = float(r["people"])
    labels = [TECH_LABEL[c] for c in codes]
    text = [[f"{v:,.0f}" if v else "" for v in row] for row in z]
    fig = go.Figure(go.Heatmap(z=z, x=labels, y=labels, text=text, texttemplate="%{text}", colorscale="Blues",
                               colorbar=dict(title="People"), hovertemplate="from %{y}<br>to %{x}<br>%{z:,.0f} people<extra></extra>"))
    fig.update_xaxes(title_text="Technology at the alternative cost")
    fig.update_yaxes(title_text="Technology at the reference cost", autorange="reversed")
    return _apply(fig, title, height=460)


def delta_bars(delta_df: pd.DataFrame, title: str, label_map: dict | None = None) -> go.Figure:
    """Percent change per metric, variant against base."""
    labels = [(label_map or {}).get(m, m) for m in delta_df["metric"]]
    colours = [ACCENT if v >= 0 else "#D55E00" for v in delta_df["delta_pct"]]
    fig = go.Figure(go.Bar(x=labels, y=delta_df["delta_pct"], marker_color=colours,
                           text=[f"{v:+.1f}%" for v in delta_df["delta_pct"]], textposition="outside",
                           hovertemplate="%{x}: %{y:+.1f}%<extra></extra>"))
    fig.update_yaxes(title_text="Change against the base case (%)", zeroline=True)
    return _apply(fig, title, height=420)


def fig_to_div(fig: go.Figure, div_id: str, height: int | None = None) -> str:
    if height:
        fig.update_layout(height=height)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=div_id,
                       config={"responsive": True, "displaylogo": False,
                               "modeBarButtonsToRemove": ["select2d", "lasso2d"]})


def plotly_js() -> str:
    """The plotly.js bundle shipped with the installed plotly package."""
    try:
        from plotly.offline import get_plotlyjs
        return get_plotlyjs()
    except ImportError:                      # pragma: no cover
        import importlib.resources as res
        return res.files("plotly").joinpath("package_data", "plotly.min.js").read_text(encoding="utf-8")

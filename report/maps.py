"""Matplotlib map builders returning PNG bytes.

Every map uses the same neatline frame: a title band, a full-width map panel with the
legend overlaid (settlement counts and population shares), a two-tone north arrow, a
0-50-100 km scale bar, and a footer with the source note and the neutral disclaimer.
Guinea only: national and regional boundaries from GADM, no neighbouring countries."""
import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Polygon  # noqa: E402

from report.constants import (DISCLAIMER, LAT_CENTER, SERVED_CODES, TECH_COLOUR, TECH_LABEL, TECH_ORDER)  # noqa: E402

DRAW_ORDER = [99, 3, 5, 7, 2, 1]            # bottom to top: unserved, stand-alone, mini-grids, grid
POINT_SIZE = {99: 1.5, 3: 2.0, 5: 7.0, 7: 9.0, 2: 6.0, 1: 6.0}
HV_COLOUR = "#3B3B3B"
KKT_COLOUR = "#B2182B"
BOUNDARY_COLOUR = "#7F7F7F"
LAND_COLOUR = "#F7F7F5"
TEXT_COLOUR = "#222222"
FONT = "DejaVu Sans"
plt.rcParams["font.family"] = FONT


# ---------------------------------------------------------------------------
# Legend
# ---------------------------------------------------------------------------
def legend_entries(df: pd.DataFrame, year: int) -> list:
    """Technology classes present in the year, in display order, with settlement counts,
    people and the share of people."""
    code = df[f"FinalElecCode{year}"]
    pop = df[f"Pop{year}"]
    total = float(pop.sum())
    out = []
    for c in TECH_ORDER:
        sel = code == c
        if not sel.any():
            continue
        people = float(pop[sel].sum())
        out.append({"code": c, "label": TECH_LABEL[c], "colour": TECH_COLOUR[c], "settlements": int(sel.sum()),
                    "people": people, "share": people / total * 100 if total else 0.0})
    return out


def legend_text(entry: dict) -> str:
    return f"{entry['label']}, {entry['settlements']:,} settlements ({entry['share']:.1f}% of people)"


# ---------------------------------------------------------------------------
# Frame
# ---------------------------------------------------------------------------
def _extent(layers, df=None, pad=0.15):
    if layers and "adm0" in layers:
        minx, miny, maxx, maxy = layers["adm0"].total_bounds
    else:
        minx, maxx = df["X_deg"].min(), df["X_deg"].max()
        miny, maxy = df["Y_deg"].min(), df["Y_deg"].max()
    return (minx - pad, maxx + pad, miny - pad, maxy + pad)


def neatline_frame(title: str, subtitle: str, source_note: str, figsize=(10, 8.5), ncols: int = 1):
    fig = plt.figure(figsize=figsize, facecolor="white")
    fig.text(0.03, 0.965, title, fontsize=15, fontweight="bold", color=TEXT_COLOUR, va="top")
    if subtitle:
        fig.text(0.03, 0.925, subtitle, fontsize=10.5, color="#444444", va="top")
    fig.add_artist(Line2D([0.03, 0.97], [0.905, 0.905], transform=fig.transFigure, color=TEXT_COLOUR, lw=1.0))
    axes = []
    width = 0.94 / ncols
    for i in range(ncols):
        ax = fig.add_axes([0.03 + i * width, 0.105, width - (0.02 if ncols > 1 else 0.0), 0.785])
        ax.set_axis_off()
        axes.append(ax)
    fig.add_artist(Line2D([0.03, 0.97], [0.095, 0.095], transform=fig.transFigure, color=TEXT_COLOUR, lw=1.0))
    fig.text(0.03, 0.072, f"Source: {source_note}", fontsize=8.5, color="#333333", va="top", wrap=True)
    fig.text(0.03, 0.040, DISCLAIMER, fontsize=7.5, color="#555555", va="top", style="italic", wrap=True)
    return fig, (axes[0] if ncols == 1 else axes)


def draw_base(ax, layers, extent):
    if layers:
        if "adm0" in layers:
            layers["adm0"].plot(ax=ax, facecolor=LAND_COLOUR, edgecolor=TEXT_COLOUR, linewidth=0.9, zorder=1)
        if "adm1" in layers:
            layers["adm1"].boundary.plot(ax=ax, color=BOUNDARY_COLOUR, linewidth=0.5, zorder=2)
            for _, r in layers["adm1"].iterrows():
                c = r.geometry.representative_point()
                ax.text(c.x, c.y, str(r.get("NAME_1", "")), fontsize=7.5, color="#555555", ha="center", va="center",
                        zorder=9, path_effects=None, alpha=0.9)
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_aspect(1 / np.cos(np.radians(LAT_CENTER)))


def draw_network(ax, layers, kkt=True):
    if not layers:
        return []
    handles = []
    if "hv_existing" in layers:
        layers["hv_existing"].plot(ax=ax, color=HV_COLOUR, linewidth=1.0, zorder=7)
        handles.append(Line2D([0], [0], color=HV_COLOUR, lw=1.2, label="Existing HV line"))
    if kkt and "kkt" in layers:
        layers["kkt"].plot(ax=ax, color=KKT_COLOUR, linewidth=1.4, linestyle=(0, (4, 2)), zorder=8)
        handles.append(Line2D([0], [0], color=KKT_COLOUR, lw=1.4, ls=(0, (4, 2)), label="Planned Koukoutamba 225 kV line"))
    return handles


def draw_north_arrow(ax, x=0.955, y=0.90, size=0.055):
    """Two-tone kite needle in axes coordinates."""
    t = ax.transAxes
    ax.add_patch(Polygon([[x, y + size], [x - size * 0.3, y - size * 0.35], [x, y - size * 0.1]], closed=True,
                         facecolor=TEXT_COLOUR, edgecolor=TEXT_COLOUR, lw=0.6, transform=t, zorder=12))
    ax.add_patch(Polygon([[x, y + size], [x + size * 0.3, y - size * 0.35], [x, y - size * 0.1]], closed=True,
                         facecolor="white", edgecolor=TEXT_COLOUR, lw=0.6, transform=t, zorder=12))
    ax.text(x, y + size + 0.012, "N", transform=t, ha="center", va="bottom", fontsize=10, fontweight="bold",
            color=TEXT_COLOUR, zorder=12)


def draw_scale_bar(ax, extent, lat_center=LAT_CENTER, segments=(0, 50, 100), height_frac=0.012):
    km_per_deg = 111.0 * np.cos(np.radians(lat_center))
    x0 = extent[0] + 0.06 * (extent[1] - extent[0])
    y0 = extent[2] + 0.05 * (extent[3] - extent[2])
    h = height_frac * (extent[3] - extent[2])
    for i in range(len(segments) - 1):
        xa, xb = x0 + segments[i] / km_per_deg, x0 + segments[i + 1] / km_per_deg
        ax.fill_between([xa, xb], y0, y0 + h, color="black" if i % 2 == 0 else "white", edgecolor="black",
                        linewidth=0.6, zorder=12)
    for s in segments:
        ax.text(x0 + s / km_per_deg, y0 - h * 0.6, f"{s} km" if s == segments[-1] else str(s), fontsize=8,
                ha="center", va="top", color=TEXT_COLOUR, zorder=12)


def _legend(ax, handles, title=None, loc="upper right"):
    leg = ax.legend(handles=handles, loc=loc, fontsize=8.5, frameon=True, framealpha=0.93, edgecolor="#BBBBBB",
                    title=title, title_fontsize=9, borderpad=0.8, labelspacing=0.5, handlelength=1.6)
    leg.set_zorder(20)
    return leg


def _tech_handles(entries, marker="o"):
    return [Line2D([0], [0], marker=marker, color="none", markerfacecolor=e["colour"], markeredgecolor="none",
                   markersize=7, label=legend_text(e)) for e in entries]


def _scatter_by_tech(ax, df, year, codes=DRAW_ORDER, size_scale=1.0):
    code = df[f"FinalElecCode{year}"]
    for c in codes:
        sel = code == c
        if sel.any():
            ax.scatter(df.loc[sel, "X_deg"], df.loc[sel, "Y_deg"], s=POINT_SIZE[c] * size_scale, c=TECH_COLOUR[c],
                       linewidths=0, zorder=3 + DRAW_ORDER.index(c) * 0.1, rasterized=True)


def _finish(fig, dpi=150) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _year_panel(ax, df, year, layers, legend_title=None):
    extent = _extent(layers, df)
    draw_base(ax, layers, extent)
    _scatter_by_tech(ax, df, year)
    net = draw_network(ax, layers)
    handles = _tech_handles(legend_entries(df, year)) + net
    _legend(ax, handles, title=legend_title)
    draw_north_arrow(ax)
    draw_scale_bar(ax, extent)


# ---------------------------------------------------------------------------
# Maps
# ---------------------------------------------------------------------------
def technology_map(df, year, layers, title, subtitle, source_note, dpi=150, figsize=(10, 8.5)) -> bytes:
    fig, ax = neatline_frame(title, subtitle, source_note, figsize)
    _year_panel(ax, df, year, layers, legend_title=f"Least-cost technology, {year}")
    return _finish(fig, dpi)


def two_panel_map(df, layers, title, source_note, subtitle="", dpi=150, figsize=(15, 7.6)) -> bytes:
    fig, axes = neatline_frame(title, subtitle, source_note, figsize, ncols=2)
    for ax, year in zip(axes, (2030, 2040)):
        _year_panel(ax, df, year, layers, legend_title=f"Least-cost technology, {year}")
        ax.set_title(str(year), fontsize=12, fontweight="bold", color=TEXT_COLOUR, loc="left", pad=4)
    return _finish(fig, dpi)


def switch_map(df_ref, df_alt, year, layers, name_ref, name_alt, title, source_note, dpi=150, figsize=(10, 8.5)) -> bytes:
    fig, ax = neatline_frame(title, f"Settlements whose least-cost technology differs between {name_ref} and {name_alt}",
                             source_note, figsize)
    extent = _extent(layers, df_ref)
    draw_base(ax, layers, extent)
    j = df_ref[["id", "X_deg", "Y_deg", f"FinalElecCode{year}", f"Pop{year}"]].merge(
        df_alt[["id", f"FinalElecCode{year}"]], on="id", suffixes=("_ref", "_alt"))
    changed = j[j[f"FinalElecCode{year}_ref"] != j[f"FinalElecCode{year}_alt"]]
    ax.scatter(j["X_deg"], j["Y_deg"], s=1.2, c="#CFCFCF", linewidths=0, zorder=3, rasterized=True)
    handles = [Line2D([0], [0], marker="o", color="none", markerfacecolor="#CFCFCF", markersize=6,
                      label=f"Unchanged, {len(j) - len(changed):,} settlements")]
    total_people = float(changed[f"Pop{year}"].sum())
    for c in [k for k in TECH_ORDER if k in SERVED_CODES]:
        sel = changed[f"FinalElecCode{year}_alt"] == c
        if sel.any():
            ax.scatter(changed.loc[sel, "X_deg"], changed.loc[sel, "Y_deg"], s=9, c=TECH_COLOUR[c], linewidths=0,
                       zorder=5, rasterized=True)
            people = float(changed.loc[sel, f"Pop{year}"].sum())
            handles.append(Line2D([0], [0], marker="o", color="none", markerfacecolor=TECH_COLOUR[c], markersize=7,
                                  label=f"Now {TECH_LABEL[c]}, {int(sel.sum()):,} settlements ({people / 1e6:.2f} M people)"))
    handles += draw_network(ax, layers)
    _legend(ax, handles, title=f"{len(changed):,} settlements switch ({total_people / 1e6:.2f} M people)")
    draw_north_arrow(ax)
    draw_scale_bar(ax, extent)
    return _finish(fig, dpi)


def status_map(df, layers, title, source_note, dpi=150, figsize=(10, 8.5)) -> bytes:
    fig, ax = neatline_frame(title, "Start-year electrification status after calibration", source_note, figsize)
    extent = _extent(layers, df)
    draw_base(ax, layers, extent)
    pop = df["PopStartYear"] if "PopStartYear" in df else df["Pop2030"]
    for flag, colour, size, label in ((0, "#C8C8C8", 1.6, "Not electrified in the start year"),
                                      (1, "#0072B2", 4.0, "Electrified in the start year")):
        sel = df["ElecStart"] == flag
        ax.scatter(df.loc[sel, "X_deg"], df.loc[sel, "Y_deg"], s=size, c=colour, linewidths=0, zorder=3 + flag,
                   rasterized=True)
    total = float(pop.sum())
    handles = [Line2D([0], [0], marker="o", color="none", markerfacecolor=colour, markersize=7,
                      label=f"{label}, {int((df['ElecStart'] == flag).sum()):,} settlements "
                            f"({float(pop[df['ElecStart'] == flag].sum()) / total * 100:.1f}% of people)")
               for flag, colour, _, label in ((1, "#0072B2", 4.0, "Electrified in the start year"),
                                              (0, "#C8C8C8", 1.6, "Not electrified in the start year"))]
    handles += draw_network(ax, layers, kkt=False)
    _legend(ax, handles, title="Electrification status, 2025")
    draw_north_arrow(ax)
    draw_scale_bar(ax, extent)
    return _finish(fig, dpi)


def hydro_map(df, layers, title, source_note, year=2040, dpi=150, figsize=(10, 8.5)) -> bytes:
    fig, ax = neatline_frame(title, f"Settlements served by hydro mini-grids in {year} and the small-hydro potential sites",
                             source_note, figsize)
    extent = _extent(layers, df)
    draw_base(ax, layers, extent)
    ax.scatter(df["X_deg"], df["Y_deg"], s=1.0, c="#D9D9D9", linewidths=0, zorder=3, rasterized=True)
    handles = []
    if layers and "mini_hydro" in layers:
        h = layers["mini_hydro"]
        ax.scatter(h.geometry.x, h.geometry.y, s=14, marker="^", c="none", edgecolors="#2B2B2B", linewidths=0.6, zorder=6)
        handles.append(Line2D([0], [0], marker="^", color="none", markerfacecolor="none", markeredgecolor="#2B2B2B",
                              markersize=7, label=f"Small-hydro potential sites, {len(h):,}"))
    sel = df[f"FinalElecCode{year}"] == 7
    ax.scatter(df.loc[sel, "X_deg"], df.loc[sel, "Y_deg"], s=16, c=TECH_COLOUR[7], linewidths=0.3, edgecolors="black",
               zorder=7)
    handles.append(Line2D([0], [0], marker="o", color="none", markerfacecolor=TECH_COLOUR[7], markeredgecolor="black",
                          markersize=8, label=f"Hydro mini-grid settlements, {int(sel.sum()):,} "
                                              f"({float(df.loc[sel, f'Pop{year}'].sum()) / 1e3:.1f} k people)"))
    handles += draw_network(ax, layers)
    _legend(ax, handles, title=f"Hydro mini-grids, {year}")
    draw_north_arrow(ax)
    draw_scale_bar(ax, extent)
    return _finish(fig, dpi)


def corridor_map(df, geo_attr, layers, radius_km, title, source_note, year=2040, dpi=150, figsize=(10, 8.5)) -> bytes:
    fig, ax = neatline_frame(title, f"Settlements within {radius_km} km of the planned Linsan to Manantali line, "
                                    f"least-cost technology in {year}", source_note, figsize)
    extent = _extent(layers, df)
    draw_base(ax, layers, extent)
    j = df.merge(geo_attr[["id", "kkt_main_dist_km"]], on="id", how="inner")
    inside = j[j["kkt_main_dist_km"] <= radius_km]
    ax.scatter(j["X_deg"], j["Y_deg"], s=1.0, c="#D9D9D9", linewidths=0, zorder=3, rasterized=True)
    handles = []
    if layers:
        if "protected_span_hv" in layers:
            layers["protected_span_hv"].plot(ax=ax, facecolor="#A6D96A", alpha=0.35, edgecolor="#4D9221", linewidth=0.6, zorder=2.5)
            handles.append(Patch(facecolor="#A6D96A", alpha=0.5, edgecolor="#4D9221", label="Protected areas crossed by the line"))
        if "affected_localities" in layers:
            layers["affected_localities"].boundary.plot(ax=ax, color="#7B3294", linewidth=1.0, zorder=6)
            handles.append(Line2D([0], [0], color="#7B3294", lw=1.2, label="Affected localities (5)"))
        if "kkt_main" in layers:
            buf = layers["kkt_main"].to_crs("EPSG:32629").buffer(radius_km * 1000).to_crs("EPSG:4326")
            buf.boundary.plot(ax=ax, color=KKT_COLOUR, linewidth=0.7, linestyle=":", zorder=6)
            handles.append(Line2D([0], [0], color=KKT_COLOUR, lw=0.9, ls=":", label=f"{radius_km} km corridor"))
    for c in [k for k in TECH_ORDER if k in SERVED_CODES]:
        sel = inside[f"FinalElecCode{year}"] == c
        if sel.any():
            ax.scatter(inside.loc[sel, "X_deg"], inside.loc[sel, "Y_deg"], s=9, c=TECH_COLOUR[c], linewidths=0, zorder=5,
                       rasterized=True)
    handles = _tech_handles(legend_entries(inside, year)) + handles + draw_network(ax, layers)
    _legend(ax, handles, title=f"Corridor settlements, {len(inside):,} ({float(inside[f'Pop{year}'].sum()) / 1e3:.0f} k people)")
    draw_north_arrow(ax)
    draw_scale_bar(ax, extent)
    return _finish(fig, dpi)


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------
def png_data_uri(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def shrink_png(png: bytes, colours: int = 64) -> bytes:
    """Palette-quantise a PNG (PIL median cut) to cut its size; colours <= 0 returns it unchanged."""
    if colours <= 0:
        return png
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    q = im.quantize(colors=colours, method=Image.Quantize.MEDIANCUT)
    out = io.BytesIO()
    q.save(out, format="PNG", optimize=True)
    return out.getvalue()

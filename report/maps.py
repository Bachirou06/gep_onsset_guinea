"""Matplotlib map builders returning PNG bytes.

Every map uses the same neatline frame: a title band, the map panel, a legend
column beside it (settlement counts and population shares), a two-tone north arrow,
a 0-50-100 km scale bar, and a footer with the source note and the neutral
disclaimer. Guinea only: national and regional boundaries from GADM, network
lines clipped to the border, no neighbouring countries. Draw order from the bottom:
not yet electrified, stand-alone PV, mini-grid PV, mini-grid hydro, grid extension,
grid densification."""
import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Polygon, Rectangle  # noqa: E402

from report.constants import (DISCLAIMER, LAT_CENTER, SERVED_CODES, TECH_COLOUR, TECH_LABEL, TECH_ORDER)  # noqa: E402

DRAW_ORDER = [99, 3, 5, 7, 2, 1]            # bottom to top
POINT_SIZE = {99: 1.5, 3: 2.0, 5: 7.0, 7: 9.0, 2: 6.0, 1: 6.0}
HV_COLOUR = "#3B3B3B"
KKT_COLOUR = "#B2182B"
BOUNDARY_COLOUR = "#7F7F7F"
LAND_COLOUR = "#F7F7F5"
TEXT_COLOUR = "#222222"
PROTECTED_FACE, PROTECTED_EDGE = "#A6D96A", "#4D9221"
LOCALITY_COLOUR = "#7B3294"
GREY_POINT, GREY_UNCHANGED, GREY_STATUS = "#D9D9D9", "#CFCFCF", "#C8C8C8"
STATUS_COLOUR = "#0072B2"
FONT = "DejaVu Sans"
plt.rcParams["font.family"] = FONT
MIN_PALETTE = 32


def zorder_of(code: int) -> float:
    return 3 + DRAW_ORDER.index(code) * 0.1


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
    return f"{entry['label']}\n{entry['settlements']:,} settlements ({entry['share']:.1f}% of people)"


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


def neatline_frame(title: str, subtitle: str, source_note: str, figsize=(11, 8.5), ncols: int = 1):
    """Title band, map axes with a legend axes beside (one panel) or below (two panels),
    footer with source and disclaimer. Returns fig, map axes (or list), legend axes (or list)."""
    fig = plt.figure(figsize=figsize, facecolor="white")
    fig.text(0.03, 0.965, title, fontsize=15, fontweight="bold", color=TEXT_COLOUR, va="top")
    if subtitle:
        fig.text(0.03, 0.925, subtitle, fontsize=10.5, color="#444444", va="top")
    fig.add_artist(Line2D([0.03, 0.97], [0.905, 0.905], transform=fig.transFigure, color=TEXT_COLOUR, lw=1.0))
    if ncols == 1:
        ax = fig.add_axes([0.03, 0.105, 0.66, 0.785])
        lax = fig.add_axes([0.705, 0.105, 0.265, 0.785])
        axes, laxes = ax, lax
    else:
        axes, laxes = [], []
        width = 0.94 / ncols
        for i in range(ncols):
            x0 = 0.03 + i * width
            axes.append(fig.add_axes([x0, 0.33, width - 0.02, 0.56]))
            laxes.append(fig.add_axes([x0, 0.105, width - 0.02, 0.21]))
    for a in (axes if isinstance(axes, list) else [axes]) + (laxes if isinstance(laxes, list) else [laxes]):
        a.set_axis_off()
    fig.add_artist(Line2D([0.03, 0.97], [0.095, 0.095], transform=fig.transFigure, color=TEXT_COLOUR, lw=1.0))
    fig.text(0.03, 0.072, f"Source: {source_note}", fontsize=8.5, color="#333333", va="top", wrap=True)
    fig.text(0.03, 0.040, DISCLAIMER, fontsize=7.5, color="#555555", va="top", style="italic", wrap=True)
    return fig, axes, laxes


def draw_base(ax, layers, extent, labels=True):
    from matplotlib import patheffects
    if layers:
        if "adm0" in layers:
            layers["adm0"].plot(ax=ax, facecolor=LAND_COLOUR, edgecolor=TEXT_COLOUR, linewidth=0.9, zorder=1)
        if "adm1" in layers:
            layers["adm1"].boundary.plot(ax=ax, color=BOUNDARY_COLOUR, linewidth=0.5, zorder=2)
            if labels:
                halo = [patheffects.withStroke(linewidth=2.5, foreground="white")]
                for _, r in layers["adm1"].iterrows():
                    c = r.geometry.representative_point()
                    if extent[0] <= c.x <= extent[1] and extent[2] <= c.y <= extent[3]:
                        ax.text(c.x, c.y, str(r.get("NAME_1", "")), fontsize=8, color="#4A4A4A", ha="center", va="center",
                                zorder=9, path_effects=halo)
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_aspect(1 / np.cos(np.radians(LAT_CENTER)))


def _clipped(layers, key):
    """A network layer clipped to the national boundary (Guinea only on the maps)."""
    g = layers[key]
    if "adm0" in layers:
        try:
            import geopandas as gpd
            return gpd.clip(g, layers["adm0"])
        except Exception:
            return g
    return g


def draw_network(ax, layers, kkt=True):
    if not layers:
        return []
    handles = []
    if "hv_existing" in layers:
        _clipped(layers, "hv_existing").plot(ax=ax, color=HV_COLOUR, linewidth=1.0, zorder=7)
        handles.append(Line2D([0], [0], color=HV_COLOUR, lw=1.2, label="Existing HV line"))
    if kkt and "kkt" in layers:
        _clipped(layers, "kkt").plot(ax=ax, color=KKT_COLOUR, linewidth=1.4, linestyle=(0, (4, 2)), zorder=8)
        handles.append(Line2D([0], [0], color=KKT_COLOUR, lw=1.4, ls=(0, (4, 2)), label="Planned Koukoutamba 225 kV line"))
    return handles


def draw_north_arrow(ax, x=0.045, y=0.90, size=0.055):
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


def _legend(lax, handles, title=None):
    """Legend in its own axes (beside or below the map), never over the data."""
    leg = lax.legend(handles=handles, loc="upper left", fontsize=8.5, frameon=False, title=title, title_fontsize=9.5,
                     borderpad=0.4, labelspacing=0.9, handlelength=1.6, borderaxespad=0.2, alignment="left")
    leg._legend_box.align = "left"
    return leg


def _swatch(colour, label, marker="o", size=7, edge="none"):
    return Line2D([0], [0], marker=marker, color="none", markerfacecolor=colour, markeredgecolor=edge, markersize=size, label=label)


def _tech_handles(entries):
    return [_swatch(e["colour"], legend_text(e)) for e in entries]


def _scatter_by_tech(ax, df, year, size_scale=1.0):
    code = df[f"FinalElecCode{year}"]
    for c in DRAW_ORDER:
        sel = code == c
        if sel.any():
            ax.scatter(df.loc[sel, "X_deg"], df.loc[sel, "Y_deg"], s=POINT_SIZE[c] * size_scale, c=TECH_COLOUR[c],
                       linewidths=0, zorder=zorder_of(c), rasterized=True)


def _finish(fig, dpi=150) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _year_panel(ax, lax, df, year, layers, legend_title=None):
    extent = _extent(layers, df)
    draw_base(ax, layers, extent)
    _scatter_by_tech(ax, df, year)
    net = draw_network(ax, layers)
    _legend(lax, _tech_handles(legend_entries(df, year)) + net, title=legend_title)
    draw_north_arrow(ax)
    draw_scale_bar(ax, extent)


# ---------------------------------------------------------------------------
# Maps
# ---------------------------------------------------------------------------
def technology_map(df, year, layers, title, subtitle, source_note, dpi=150, figsize=(11, 8.5)) -> bytes:
    fig, ax, lax = neatline_frame(title, subtitle, source_note, figsize)
    _year_panel(ax, lax, df, year, layers, legend_title=f"Least-cost technology, {year}")
    return _finish(fig, dpi)


def two_panel_map(df, layers, title, source_note, subtitle="", dpi=150, figsize=(15, 9.2)) -> bytes:
    fig, axes, laxes = neatline_frame(title, subtitle, source_note, figsize, ncols=2)
    for ax, lax, year in zip(axes, laxes, (2030, 2040)):
        _year_panel(ax, lax, df, year, layers, legend_title=f"Least-cost technology, {year}")
        ax.set_title(str(year), fontsize=12, fontweight="bold", color=TEXT_COLOUR, loc="left", pad=4)
    return _finish(fig, dpi)


def switch_map(df_ref, df_alt, year, layers, name_ref, name_alt, title, source_note, dpi=150, figsize=(11, 8.5)) -> bytes:
    fig, ax, lax = neatline_frame(title, f"Settlements whose least-cost technology differs between {name_ref} and {name_alt}",
                                  source_note, figsize)
    extent = _extent(layers, df_ref)
    draw_base(ax, layers, extent)
    j = df_ref[["id", "X_deg", "Y_deg", f"FinalElecCode{year}", f"Pop{year}"]].merge(
        df_alt[["id", f"FinalElecCode{year}"]], on="id", suffixes=("_ref", "_alt"))
    changed = j[j[f"FinalElecCode{year}_ref"] != j[f"FinalElecCode{year}_alt"]]
    ax.scatter(j["X_deg"], j["Y_deg"], s=1.2, c=GREY_UNCHANGED, linewidths=0, zorder=3, rasterized=True)
    handles = [_swatch(GREY_UNCHANGED, f"Unchanged\n{len(j) - len(changed):,} settlements")]
    total_people = float(changed[f"Pop{year}"].sum())
    for c in [k for k in DRAW_ORDER if k in SERVED_CODES]:
        sel = changed[f"FinalElecCode{year}_alt"] == c
        if sel.any():
            ax.scatter(changed.loc[sel, "X_deg"], changed.loc[sel, "Y_deg"], s=9, c=TECH_COLOUR[c], linewidths=0,
                       zorder=zorder_of(c) + 1, rasterized=True)
            people = float(changed.loc[sel, f"Pop{year}"].sum())
            handles.append(_swatch(TECH_COLOUR[c], f"Now {TECH_LABEL[c].lower()}\n{int(sel.sum()):,} settlements ({people / 1e6:.2f} M people)"))
    handles += draw_network(ax, layers)
    _legend(lax, handles, title=f"{len(changed):,} settlements switch\n({total_people / 1e6:.2f} M people)")
    draw_north_arrow(ax)
    draw_scale_bar(ax, extent)
    return _finish(fig, dpi)


def status_map(df, layers, title, source_note, dpi=150, figsize=(11, 8.5)) -> bytes:
    fig, ax, lax = neatline_frame(title, "Settlements classed as electrified or not in 2025 after calibration to the national statistics",
                                  source_note, figsize)
    extent = _extent(layers, df)
    draw_base(ax, layers, extent)
    pop = df["PopStartYear"] if "PopStartYear" in df else df["Pop2030"]
    total = float(pop.sum())
    for flag, colour, size in ((0, GREY_STATUS, 1.6), (1, STATUS_COLOUR, 4.0)):
        sel = df["ElecStart"] == flag
        ax.scatter(df.loc[sel, "X_deg"], df.loc[sel, "Y_deg"], s=size, c=colour, linewidths=0, zorder=3 + flag, rasterized=True)
    handles = []
    for flag, colour, label in ((1, STATUS_COLOUR, "Electrified in the start year"), (0, GREY_STATUS, "Not electrified in the start year")):
        sel = df["ElecStart"] == flag
        handles.append(_swatch(colour, f"{label}\n{int(sel.sum()):,} settlements ({float(pop[sel].sum()) / total * 100:.1f}% of people)"))
    handles += draw_network(ax, layers, kkt=False)
    _legend(lax, handles, title="Electrification status, 2025")
    draw_north_arrow(ax)
    draw_scale_bar(ax, extent)
    return _finish(fig, dpi)


def hydro_map(df, layers, title, source_note, year=2040, dpi=150, figsize=(11, 8.5)) -> bytes:
    fig, ax, lax = neatline_frame(title, f"Settlements served by hydro mini-grids in {year} and the small-hydro potential sites",
                                  source_note, figsize)
    extent = _extent(layers, df)
    draw_base(ax, layers, extent)
    ax.scatter(df["X_deg"], df["Y_deg"], s=1.0, c=GREY_POINT, linewidths=0, zorder=3, rasterized=True)
    handles = [_swatch(GREY_POINT, f"All settlements\n{len(df):,}")]
    if layers and "mini_hydro" in layers:
        h = layers["mini_hydro"]
        ax.scatter(h.geometry.x, h.geometry.y, s=14, marker="^", c="none", edgecolors="#2B2B2B", linewidths=0.6, zorder=6)
        handles.append(Line2D([0], [0], marker="^", color="none", markerfacecolor="none", markeredgecolor="#2B2B2B",
                              markersize=7, label=f"Small-hydro potential sites\n{len(h):,} sites"))
    sel = df[f"FinalElecCode{year}"] == 7
    ax.scatter(df.loc[sel, "X_deg"], df.loc[sel, "Y_deg"], s=16, c=TECH_COLOUR[7], linewidths=0.3, edgecolors="black", zorder=7)
    handles.append(_swatch(TECH_COLOUR[7], f"Hydro mini-grid settlements, {year}\n{int(sel.sum()):,} settlements "
                                           f"({float(df.loc[sel, f'Pop{year}'].sum()) / 1e3:.1f} k people)", size=8, edge="black"))
    handles += draw_network(ax, layers)
    _legend(lax, handles, title=f"Hydro mini-grids, {year}")
    draw_north_arrow(ax)
    draw_scale_bar(ax, extent)
    return _finish(fig, dpi)


def corridor_map(df, geo_attr, layers, radius_km, title, source_note, year=2040, dpi=150, figsize=(11, 8.5)) -> bytes:
    """Zoomed to the corridor, with the national outline as an inset for orientation."""
    fig, ax, lax = neatline_frame(title, f"Settlements within {radius_km} km of the planned Linsan to Manantali line, "
                                         f"least-cost technology in {year}", source_note, figsize)
    j = df.merge(geo_attr[["id", "kkt_main_dist_km"]], on="id", how="inner")
    inside = j[j["kkt_main_dist_km"] <= radius_km]
    buf = None
    if layers and "kkt_main" in layers:
        buf = layers["kkt_main"].to_crs("EPSG:32629").buffer(radius_km * 1000).to_crs("EPSG:4326")
        bx = buf.total_bounds
        extent = (bx[0] - 0.35, bx[2] + 0.35, bx[1] - 0.35, bx[3] + 0.35)
    else:
        extent = _extent(None, inside if len(inside) else df, pad=0.3)
    draw_base(ax, layers, extent)
    ax.scatter(j["X_deg"], j["Y_deg"], s=1.2, c=GREY_POINT, linewidths=0, zorder=3, rasterized=True)
    handles = []
    if layers:
        if "protected_span_hv" in layers:
            layers["protected_span_hv"].plot(ax=ax, facecolor=PROTECTED_FACE, alpha=0.45, edgecolor=PROTECTED_EDGE, linewidth=0.8, zorder=3.5)
            handles.append(Patch(facecolor=PROTECTED_FACE, alpha=0.6, edgecolor=PROTECTED_EDGE, label="Protected areas crossed by the line"))
        if "affected_localities" in layers:
            layers["affected_localities"].boundary.plot(ax=ax, color=LOCALITY_COLOUR, linewidth=1.3, zorder=6)
            handles.append(Line2D([0], [0], color=LOCALITY_COLOUR, lw=1.3, label="Affected localities (5)"))
        if buf is not None:
            buf.boundary.plot(ax=ax, color=KKT_COLOUR, linewidth=0.8, linestyle=":", zorder=6)
            handles.append(Line2D([0], [0], color=KKT_COLOUR, lw=0.9, ls=":", label=f"{radius_km} km corridor"))
    for c in [k for k in DRAW_ORDER if k in SERVED_CODES]:
        sel = inside[f"FinalElecCode{year}"] == c
        if sel.any():
            ax.scatter(inside.loc[sel, "X_deg"], inside.loc[sel, "Y_deg"], s=12, c=TECH_COLOUR[c], linewidths=0,
                       zorder=zorder_of(c) + 1, rasterized=True)
    handles = _tech_handles(legend_entries(inside, year)) + handles + draw_network(ax, layers)
    _legend(lax, handles, title=f"Corridor settlements\n{len(inside):,} settlements ({float(inside[f'Pop{year}'].sum()) / 1e3:.0f} k people)")
    draw_north_arrow(ax)
    draw_scale_bar(ax, extent)
    if layers and "adm0" in layers:
        ins = ax.inset_axes([0.70, 0.02, 0.29, 0.29])
        ins.set_axis_off()
        layers["adm0"].plot(ax=ins, facecolor=LAND_COLOUR, edgecolor=TEXT_COLOUR, linewidth=0.6)
        if "kkt_main" in layers:
            _clipped(layers, "kkt_main").plot(ax=ins, color=KKT_COLOUR, linewidth=0.9, linestyle=(0, (4, 2)))
        ins.add_patch(Rectangle((extent[0], extent[2]), extent[1] - extent[0], extent[3] - extent[2], fill=False,
                                edgecolor=TEXT_COLOUR, linewidth=0.8))
        ins.set_aspect(1 / np.cos(np.radians(LAT_CENTER)))
    return _finish(fig, dpi)


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------
def png_data_uri(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _blend(hex_colour: str, white_frac: float):
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(int(round(v + (255 - v) * white_frac)) for v in (r, g, b))


def fixed_palette(colours: int) -> list:
    """The map's own colours (every technology, line, boundary, land, greys), their tints for
    anti-aliasing, and a grey ramp, as a list of RGB triples of length `colours`."""
    base = [TECH_COLOUR[c] for c in TECH_ORDER] + [HV_COLOUR, KKT_COLOUR, BOUNDARY_COLOUR, LAND_COLOUR, TEXT_COLOUR,
                                                    PROTECTED_FACE, PROTECTED_EDGE, LOCALITY_COLOUR, GREY_POINT,
                                                    GREY_UNCHANGED, GREY_STATUS, STATUS_COLOUR, "#FFFFFF", "#000000"]
    pal = [_blend(c, 0.0) for c in base]
    for frac in (0.25, 0.5, 0.75):
        pal += [_blend(c, frac) for c in base[:8]]            # tints of the technology and line colours
    greys = [(v, v, v) for v in np.linspace(40, 250, 24).astype(int)]
    pal += [g for g in greys if g not in pal]
    pal = list(dict.fromkeys(pal))
    if len(pal) > colours:
        pal = pal[:colours]
    return pal


def shrink_png(png: bytes, colours: int = 96) -> bytes:
    """Quantise a PNG to a FIXED palette built from the map's own colours, so no technology
    class can vanish (median cut dropped rare classes). colours <= 0 returns the input;
    fewer than MIN_PALETTE colours is refused."""
    if colours <= 0:
        return png
    if colours < MIN_PALETTE:
        raise ValueError(f"map quantisation needs at least {MIN_PALETTE} colours to keep every class; got {colours}")
    from PIL import Image
    pal = fixed_palette(colours)
    pal_img = Image.new("P", (1, 1))
    flat = [v for rgb in pal for v in rgb]
    pal_img.putpalette(flat + [0] * (768 - len(flat)))
    im = Image.open(io.BytesIO(png)).convert("RGB")
    q = im.quantize(palette=pal_img, dither=Image.Dither.NONE)
    out = io.BytesIO()
    q.save(out, format="PNG", optimize=True)
    return out.getvalue()

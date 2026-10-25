"""Patch GEP_Generator.ipynb so its scenario section runs from the control file.

Run once from the repository root:  python tools/patch_notebook.py

What it does (kept as a script so the edit is reproducible and reviewable):
  1. cell 2: the absolute sys.path to a personal folder becomes a path relative
     to the notebook (gep_onsset/ next to it);
  2. cells 43 to 64 (population threshold, demand, scenario loop, summaries,
     charts, export) are removed: that code now lives in gep_onsset/scenario_runner.py;
  3. a new section 7 is appended: pick a scenario id from Scenarios/guinea_scenarios.json,
     run it, show its summary table and the four-panel chart;
  4. empty trailing code cells are dropped and all outputs are stripped.
Idempotent: a notebook already patched is left unchanged.
"""
import sys
from pathlib import Path

import nbformat

REPO = Path(__file__).resolve().parents[1]
NOTEBOOK = REPO / "GEP_Generator.ipynb"

SYS_PATH_OLD = "sys.path.append(r'C:\\Users\\Bachirou\\Documents\\gep_onsset_guinea\\gep_onsset')"
SYS_PATH_NEW = "import os\nsys.path.append(os.path.join(os.getcwd(), 'gep_onsset'))"

MARKDOWN = """# 7. Run a scenario from the control file

Scenario levers (demand tiers, grid generation cost, connection caps, technology switches, costs) are no
longer typed in this notebook. They come from `Scenarios/guinea_scenarios.json`, which lists every
scenario of the study with every lever explicit, and they are executed by `gep_onsset/scenario_runner.py`,
the same code path as the command line:

    python run_scenarios.py Scenarios/guinea_scenarios.json --only BU_g0.1

The cells above (sections 1 to 5) remain the interactive calibration front end. Their lever values apply
to the calibration step only; the control file's `calibration` block must say the same.

Outputs land under `GuineaRuns/Outputs/notebook/<scenario_id>/` as the three CSVs this notebook used to
write (`_Results`, `_Summaries`, `_Variables`) plus a `manifest.json` recording every parameter, the
input file hash and the code version.
"""

RUN_CELL = """from scenario_control import load_control
from scenario_runner import run_scenario, summary_from_manifest

control = load_control('Scenarios/guinea_scenarios.json')
print('Scenarios:', control.ids())

scenario_id = 'BU_g0.1'          # change to any id listed above
batch_dir = control.paths['output_root'] / 'notebook'
manifest = run_scenario(control, scenario_id, batch_dir, force=True)
summary_table = summary_from_manifest(batch_dir, scenario_id)
yearsofanalysis = [control.defaults['intermediate_year'], control.defaults['end_year']]
summary_table
"""

CHART_CELL = """import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# Technologies in the order of summary_table (without the Total row)
summary_plot = summary_table.drop(labels='Total', axis=0)
tech_names = summary_plot.index.tolist()
tech_colors = {'Grid_dens': '#4e53de', 'Grid_ext': '#a6aaff', 'SA_PV': '#ffc700',
               'MG_PV_Battery': '#e628a0', 'MG_PV': '#e628a0', 'MG_Hydro': '#28e66d',
               'Non-electrified': '#D3D3D3'}
bar_colors = [tech_colors.get(t, '#808080') for t in tech_names]

# The four indicators, one panel each. {y} is replaced by each year of analysis.
panels = [('Population{y}', 'Population'),
          ('NewConnections{y}', 'New connections'),
          ('Capacity{y} (MW)', 'Capacity (MW)'),
          ('Investment{y} (million USD)', 'Investment (million USD)')]

years = list(yearsofanalysis)          # e.g. [2030, 2040]
n_years = len(years)
width = 0.8 / n_years
x = np.arange(len(tech_names))
alphas = np.linspace(0.45, 1.0, n_years)        # earlier year lighter, last year solid
hatches = ['//', '\\\\\\\\', '..', ''][:n_years - 1] + ['']

fig, axarr = plt.subplots(2, 2, figsize=(18, 12))
for ax, (pattern, title) in zip(axarr.flatten(), panels):
    for i, yr in enumerate(years):
        col = pattern.format(y=yr)
        offset = (i - (n_years - 1) / 2) * width
        ax.bar(x + offset, summary_plot[col].astype(float), width=width * 0.95,
               color=bar_colors, alpha=alphas[i], hatch=hatches[i], edgecolor='white', linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(tech_names, rotation=30, ha='right', fontsize=11)
    ax.set_ylabel(title, fontsize=13)
    ax.set_title(title, fontsize=14)
    ax.tick_params(axis='y', labelsize=11)

# One legend for the years (same colours, different shading)
handles = [Patch(facecolor='#808080', alpha=alphas[i], hatch=hatches[i], edgecolor='white', label=str(yr))
           for i, yr in enumerate(years)]
fig.legend(handles=handles, loc='upper right', fontsize=12, title='Year')
plt.tight_layout()
plt.show()
"""

FIRST_REMOVED = 43   # markdown "In some cases it can be of interest to filter out clusters..."
LAST_REMOVED = 64    # code: export of the three CSVs


def patch(nb):
    code0 = nb.cells[2].source
    if "run_scenario(" in "".join(c.source for c in nb.cells if c.cell_type == "code"):
        return False                                   # already patched
    assert SYS_PATH_OLD in code0, "cell 2 does not hold the expected sys.path line"
    nb.cells[2].source = code0.replace(SYS_PATH_OLD, SYS_PATH_NEW)

    head = nb.cells[:FIRST_REMOVED]
    tail = [c for c in nb.cells[LAST_REMOVED + 1:] if c.source.strip()]
    new = [nbformat.v4.new_markdown_cell(MARKDOWN),
           nbformat.v4.new_code_cell(RUN_CELL),
           nbformat.v4.new_code_cell(CHART_CELL)]
    nb.cells = head + new + tail

    for c in nb.cells:
        if c.cell_type == "code":
            c.outputs = []
            c.execution_count = None
    return True


def main():
    nb = nbformat.read(NOTEBOOK, as_version=4)
    changed = patch(nb)
    if changed:
        nbformat.write(nb, NOTEBOOK)
        print(f"patched {NOTEBOOK.name}: {len(nb.cells)} cells")
    else:
        print("already patched, nothing to do")
    return 0


if __name__ == "__main__":
    sys.exit(main())

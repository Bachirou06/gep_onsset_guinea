"""
guinea_demand_customization.py

Customized electricity demand module for the Guinea GEP-OnSSET scenario, inspired by
Thierry's Senegal Excel interface, adapted to run against the BASE onsset.py already
used in GEP_Generator.ipynb -- no switch to onsset_reto.py required.

Three demand layers:

  1. MTF Residential demand
     Already handled by onsset.py's set_residential_demand() using ResidentialDemandTier1-5.
     Nothing to do here -- independent of everything below (see note on 'preference' below).

  2. Social facility demand (Health, Education)
     Computed from EXACT per-settlement facility counts and tiers already in your Guinea
     extraction CSV (has_hc/hc_category/hc_count, has_edu/edu_category/edu_count -- from
     process_health_facilities()/process_educational_facilities() built earlier). This is
     more precise than Thierry's population-bin density estimate for these two categories,
     since your facilities are real GIS locations, not a statistical average.

     Health tier intensities are taken from Thierry's HealthCenterProfile sheet (WHO-sourced):
     Community 5.68 kWh/day, Primary 37.03 kWh/day, Referral 361.11 kWh/day.
     Education tier intensities are adapted proxies (HealthCenterProfile is health-only) --
     see EDU_TIER_KWH_PER_YEAR below; recalibrate when better Guinea-specific data exists.

  3. Productive demand (Agriculture, Commercial, and Community-type facilities)
     Loaded directly from Thierry's authoritative productive_uses_matrix.json (population-bin
     density x energy intensity x utilisation factor), exactly as exported by his
     ConstructFacilityPopBins sheet / onsset_reto.py's compute_productive_demand_from_matrix().

     IMPORTANT: the JSON routes Primary/Secondary school and all three health tiers into
     EducationDemand/HealthDemand via population-bin density -- these DO genuinely overlap
     with the exact GIS facility data in step 2, so they are excluded BY SLUG (see
     EXCLUDED_FACILITY_SLUGS below) to avoid double-counting real school/health buildings.

     Places of worship, Municipal office, and Public lighting cluster also route to
     EducationDemand in the JSON, but they are NOT covered by your exact edu_category/
     edu_count data at all (that only captures col_edu/lyc_edu/uni_edu -- colleges, lycees,
     universities). So these three are DELIBERATELY KEPT and ADDED on top of the exact
     school-based EducationDemand, rather than excluded -- excluding them would just discard
     real demand you have no other way of capturing, not prevent double-counting.

     Because of this, EducationDemand = exact college/lycee/universite demand (step 2)
     + community-facility demand from the matrix (worship/municipal/lighting). HealthDemand
     stays purely from exact facility data, since all three health-tier matrix rows are excluded.
     Excluded/included facilities are printed at runtime so this is never silent.

     'preference' (Low/Medium/High) selects which energy-intensity column is used from the
     matrix. This is INDEPENDENT of the residential MTF tier -- see the standalone discussion
     we had: there is no code path linking set_residential_demand()'s tier choice to this
     preference value. Every facility in the current JSON has preference='Low' hardcoded at
     export time; pass preference='Medium'/'High' here to override that for a given scenario
     run without needing to hand-edit the JSON.

Usage in GEP_Generator.ipynb, after calibration, BEFORE the yearsofanalysis scenario loop:

    from guinea_demand_customization import apply_customized_demand
    onsseter = apply_customized_demand(
        onsseter,
        matrix_path=r'C:\\path\\to\\productive_uses_matrix.json',
        preference='Low',   # or 'Medium' / 'High' -- independent of residential tier
    )

This overwrites the flat HealthDemand=0 / EducationDemand=0 / AgriDemand=0 / CommercialDemand=0
placeholders (added earlier just to satisfy condition_df()) with real computed values. From
there, onsset.py's own estimating_non_residential_loads() propagates these forward year by year
inside the scenario loop exactly as it already does -- no changes needed to onsset.py itself.
"""

import json

import pandas as pd


# =============================================================================
# 2. SOCIAL FACILITY DEMAND (Health, Education) -- exact facility counts
# =============================================================================

# kWh/year per facility, keyed by the RAW STRING category codes (com_hc/primary_hc/
# referral_hc, col_edu/lyc_edu/uni_edu) used throughout process_health_facilities()/
# process_educational_facilities().
#
# IMPORTANT: as of social_infra_admin2_extraction_v2.py, demand is computed from the
# PER-TIER count columns (hc_count_com_hc, hc_count_primary_hc, hc_count_referral_hc,
# and equivalently edu_count_col_edu/edu_count_lyc_edu/edu_count_uni_edu) -- NOT from
# hc_category/hc_count. The original version multiplied the TOTAL blended hc_count by
# only the highest-priority tier's intensity, which silently inflated demand for any
# settlement with a mix of tiers (e.g. 5 community posts + 1 hospital nearby got charged
# as if all 6 were hospitals). Fixed here by summing count_per_tier x intensity_per_tier
# across all tiers independently.

HEALTH_TIER_KWH_PER_YEAR = {
    'com_hc': 5.68 * 365,        # Community-level: 5.68 kWh/day (HealthCenterProfile)
    'primary_hc': 37.03 * 365,   # Primary-level:   37.03 kWh/day
    'referral_hc': 361.11 * 365, # Referral-level: 361.11 kWh/day
}

# NOTE: proxy values, not sourced from HealthCenterProfile (health-only sheet). Adapted from
# productive_uses_matrix.json's Primary school (1800 kWh/yr Low) / Secondary school
# (3500 kWh/yr Low) entries. Recalibrate against Guinea-specific data before treating as final.
EDU_TIER_KWH_PER_YEAR = {
    'col_edu': 1800.0,    # College (lower secondary)  proxy: Primary school, Low pref.
    'lyc_edu': 3500.0,    # Lycee (upper secondary)     proxy: Secondary school, Low pref.
    'uni_edu': 7000.0,    # Universite                  rough placeholder, 2x Lycee
}


def compute_health_demand(df, prefix='hc'):
    """HealthDemand (kWh/year) = sum over tiers of (hc_count_<tier> * intensity[<tier>])

    Uses the per-tier count columns (hc_count_com_hc / hc_count_primary_hc /
    hc_count_referral_hc) from social_infra_admin2_extraction_v2.py -- NOT the blended
    hc_category/hc_count pair, which mixes tiers together (see module docstring).
    """
    demand = pd.Series(0.0, index=df.index)
    for tier, intensity in HEALTH_TIER_KWH_PER_YEAR.items():
        col = f'{prefix}_count_{tier}'
        if col in df.columns:
            demand += df[col].fillna(0) * intensity
        else:
            print(f'WARNING: expected column "{col}" not found -- did you re-run the '
                  f'v2 extraction functions and re-export the CSV? Falling back to 0 for this tier.')
    return demand


def compute_education_demand(df, prefix='edu'):
    """EducationDemand (kWh/year) = sum over tiers of (edu_count_<tier> * intensity[<tier>])

    Same per-tier logic as compute_health_demand() -- see there for details.
    """
    demand = pd.Series(0.0, index=df.index)
    for tier, intensity in EDU_TIER_KWH_PER_YEAR.items():
        col = f'{prefix}_count_{tier}'
        if col in df.columns:
            demand += df[col].fillna(0) * intensity
        else:
            print(f'WARNING: expected column "{col}" not found -- did you re-run the '
                  f'v2 extraction functions and re-export the CSV? Falling back to 0 for this tier.')
    return demand


# =============================================================================
# 3. PRODUCTIVE DEMAND -- loaded from Thierry's authoritative JSON
# =============================================================================

def load_productive_uses_matrix(matrix_path):
    """Load productive_uses_matrix.json (as exported by ConstructFacilityPopBins)."""
    with open(matrix_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def assign_population_bins(df, population_bins, pop_col='PopStartYear'):
    """Assign a population-bin label to each settlement, using the 'population_bins'
    list straight from the JSON (label/min/max). Defaults to calibrated start-year
    population (PopStartYear), matching onsset_reto.py's SET_POP_CALIB convention.
    """
    bins_col = pd.Series('', index=df.index)
    for b in population_bins:
        if b['max'] is None:
            mask = df[pop_col] >= b['min']
        else:
            mask = (df[pop_col] >= b['min']) & (df[pop_col] < b['max'])
        bins_col.loc[mask] = b['label']
    return bins_col


# Facilities excluded from the matrix because they genuinely overlap with the exact
# GIS facility data in step 2 (real school buildings, real health facilities). Matched
# by 'slug' rather than facility_group/onsset_demand_field, since Community-type items
# (worship, municipal office, public lighting) also route to EducationDemand but are
# NOT covered by exact edu_category/edu_count data -- they must stay included.
EXCLUDED_FACILITY_SLUGS = {
    'primary_school',
    'secondary_school',
    'community_level_health_facility',
    'primary_level_health_facility',
    'referral_level_health_facility',
}


def compute_productive_demand(df, matrix, pop_bin_col='PopBin', preference='Low',
                              exclude_slugs=EXCLUDED_FACILITY_SLUGS):
    """Compute demand (kWh/year) from the productive-uses matrix, excluding facilities
    by slug (default: real schools + real health facilities, already covered exactly
    in step 2 above). Community-type facilities that happen to share an onsset_demand_field
    with an excluded slug (e.g. Places of worship -> EducationDemand) are NOT excluded --
    only exact overlaps are.

    Returns
    -------
    dict of {onsset_demand_field: pandas Series} for every field with at least one
    included facility (typically AgriDemand, CommercialDemand, EducationDemand).
    """
    facilities = matrix['facilities']
    results = {}
    included_names = []
    excluded_names = []

    for facility in facilities:
        field = facility['onsset_demand_field']

        if facility['slug'] in exclude_slugs:
            excluded_names.append(f"{facility['name']} -> {field}")
            continue

        included_names.append(f"{facility['name']} -> {field}")

        energy = facility['energy_intensity_kwh_per_year'].get(
            preference, facility['energy_intensity_kwh_per_year'].get('Low', 0.0))
        util = facility['utilisation_factor']
        counts_by_bin = facility['expected_count_by_bin']

        contribution = pd.Series(0.0, index=df.index)
        for bin_label, count in counts_by_bin.items():
            mask = df[pop_bin_col] == bin_label
            contribution.loc[mask] = count * energy * util

        if field not in results:
            results[field] = pd.Series(0.0, index=df.index)
        results[field] += contribution

    print('Productive-uses matrix -- facilities INCLUDED (Agri/Commercial etc.):')
    for name in included_names:
        print('   +', name)
    print('Productive-uses matrix -- facilities EXCLUDED (covered exactly via GIS facility data):')
    for name in excluded_names:
        print('   -', name)

    return results


# =============================================================================
# TOP-LEVEL ENTRY POINT
# =============================================================================

def apply_customized_demand(onsseter, matrix_path, pop_col='PopStartYear', preference='Low'):
    """Apply all three demand layers to onsseter.df, overwriting the flat-zero
    HealthDemand/EducationDemand/AgriDemand/CommercialDemand placeholders with real
    computed values.

    Call this ONCE, right after calibration, before the yearsofanalysis scenario loop
    in GEP_Generator.ipynb.

    preference : 'Low' / 'Medium' / 'High' -- selects the productive-uses energy-intensity
        tier from the matrix. Independent of the residential MTF tier (see module docstring).
    """
    df = onsseter.df
    matrix = load_productive_uses_matrix(matrix_path)

    # 2. Social facility demand -- exact facility counts, no density estimation needed
    df['HealthDemand'] = compute_health_demand(df)
    df['EducationDemand'] = compute_education_demand(df)

    # 3. Productive demand -- population-bin density matrix.
    # Fields with no exact-facility counterpart (AgriDemand, CommercialDemand) are set
    # fresh. EducationDemand gets the matrix's community-facility contribution ADDED on
    # top of the exact school-based value already set above (see module docstring) --
    # never overwritten, since both are genuine, non-overlapping demand sources.
    df['PopBin'] = assign_population_bins(df, matrix['population_bins'], pop_col=pop_col)
    productive_results = compute_productive_demand(df, matrix, pop_bin_col='PopBin',
                                                    preference=preference)
    for field, series in productive_results.items():
        if field in df.columns and field in ('HealthDemand', 'EducationDemand'):
            df[field] = df[field] + series   # add to exact-facility baseline
        else:
            df[field] = series                # AgriDemand/CommercialDemand: no baseline to add to

    print('\nCustomized demand applied (preference={}):'.format(preference))
    print('  HealthDemand      total {:,.0f} kWh/yr'.format(df['HealthDemand'].sum()))
    print('  EducationDemand   total {:,.0f} kWh/yr'.format(df['EducationDemand'].sum()))
    for field in productive_results:
        if field in ('HealthDemand', 'EducationDemand'):
            continue   # already printed above (exact + matrix combined)
        print('  {:<18} total {:,.0f} kWh/yr'.format(field, df[field].sum()))

    onsseter.df = df
    return onsseter

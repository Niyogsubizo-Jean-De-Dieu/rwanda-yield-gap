"""
Collect the project outputs into docs/data.js for the interactive dashboard (docs/index.html).
Run on your PC after build_model_dataset.py, train_model.py (and optionally compare_models.py):

    python3 src/build_dashboard_data.py

Inputs (defaults; all are aggregated / district level, no microdata goes into the dashboard)
    data/sas_district_yield_panel.csv         NISR published district yields 2017-2026 (trend baseline)
    data/model_data/district_crop_summary.csv    survey-weighted adoption rates and yields 2022-2025
    data/model_outputs/                       scenario_*, dose_response, feature_importance, importance_by_crop,
                                              driver_groups, validation_metrics, model_features.json
    data/model_outputs/walk_forward/          scores_by_model.csv, scores_by_season.csv (optional)
Output
    docs/data.js   (open docs/index.html in a browser; GitHub Pages publishes the docs/ folder)
"""
import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

CROPS = ["Maize", "Bush bean", "Climbing bean", "Irish potato", "Sweet potato", "Cassava", "Sorghum", "Soybean",
         "Wheat"]
GROUPS = {
    "Management (inputs & practices)": ["improved_seed", "organic_fert", "inorganic_fert", "inorganic_kg_ha", "lime",
                                        "micronutrient", "pesticide", "erosion_degree", "anti_erosion",
                                        "consolidated_site", "mechanized", "irrigated"],
    "Plot & farmer": ["log_plot_area", "crop_share", "farmer_age", "stratum", "farmer_sex"],
    "Soil & terrain": ["soil_ph", "soil_org_carbon_gkg", "soil_nitrogen_gkg", "elevation_m", "slope_deg",
                       "share_slope_gt16deg", "cropland_ha"],
}


def rnd(df, nd=3):
    return df.round(nd).replace({np.nan: None})


def rows(df):
    return {"cols": list(df.columns), "rows": rnd(df).values.tolist()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="data/sas_district_yield_panel.csv")
    ap.add_argument("--summary", default="data/model_data/district_crop_summary.csv")
    ap.add_argument("--outputs", default="data/model_outputs")
    ap.add_argument("--out", default="docs/data.js")
    a = ap.parse_args()
    o = Path(a.outputs)
    D = {"meta": {"generated": date.today().isoformat()}}

    # ---- trend baseline: NISR published district yields
    p = pd.read_csv(a.panel)
    p = p[p.crop.isin(CROPS) & p.season.isin(["A", "B"]) &
          ~p.quality_flag.fillna("").isin(["extreme_value", "season_C_sites_only"])]
    p["flag"] = p.quality_flag.fillna("")
    D["trend"] = rows(p[["crop", "season", "district", "year", "yield_kg_ha", "flag"]]
                      .sort_values(["crop", "season", "district", "year"]))
    D["provinces"] = p.drop_duplicates("district").set_index("district").province.to_dict()

    # ---- adoption from the microdata (district + national, survey-weighted by area)
    s = pd.read_csv(a.summary)
    s = s[s.crop.isin(CROPS)]
    keep = {"inorganic_fert_share_area": "fert", "improved_seed_share_area": "seed",
            "organic_fert_share_area": "manure", "lime_share_area": "lime", "anti_erosion_share_area": "antierosion"}
    s = s.rename(columns=keep)

    def nat(g):
        w = g.weighted_area_ha
        r = {"plots": g.plots.sum(), "weighted_area_ha": w.sum(), "yield_kg_ha": np.average(g.yield_kg_ha, weights=w)}
        for c in keep.values():
            m = g[c].notna()
            r[c] = np.average(g.loc[m, c], weights=w[m]) if m.any() else np.nan
        return pd.Series(r)
    n = s.groupby(["year", "season", "crop"]).apply(nat).reset_index().assign(district="Rwanda")
    ad = pd.concat([s, n], ignore_index=True)
    D["adoption"] = rows(ad[["year", "season", "district", "crop", "plots", "weighted_area_ha", "yield_kg_ha"]
                            + list(keep.values())])

    # ---- scenarios, dose-response
    sd = pd.read_csv(o / "scenario_district.csv")
    D["scenario"] = rows(sd[["scenario", "season", "district", "crop", "levers", "plots", "area_ha",
                             "current_yield_kg_ha", "adoption_pct", "yield_gain_pct", "current_production_t",
                             "extra_production_t", "attainable_yield_kg_ha"]])
    sn = pd.read_csv(o / "scenario_national.csv")
    D["scenario_nat"] = rows(sn[["scenario", "season", "crop", "levers", "area_ha", "current_yield_kg_ha",
                                 "adoption_pct", "yield_gain_pct", "current_production_t", "extra_production_t"]])
    D["meta"]["scenario_year"] = int(sd.year.max())
    D["dose"] = rows(pd.read_csv(o / "dose_response.csv"))

    # ---- drivers (SHAP)
    fi = pd.read_csv(o / "feature_importance.csv")
    D["meta"]["driver_method"] = str(fi.method.iloc[0])
    fi = fi[fi.share_pct.notna()]
    D["drivers"] = rows(fi[["feature", "group", "share_pct"]])
    bc = pd.read_csv(o / "importance_by_crop.csv").set_index("feature")
    bc = bc.drop(index=[f for f in ["crop", "season"] if f in bc.index])
    bc = 100 * bc / bc.sum()
    grp = {f: g for g, fs in GROUPS.items() for f in fs}
    bc_long = bc.reset_index().melt(id_vars="feature", var_name="crop", value_name="share_pct")
    bc_long["group"] = bc_long.feature.map(grp).fillna("Season weather (satellite)")
    D["drivers_crop"] = rows(bc_long[["crop", "feature", "group", "share_pct"]])

    # ---- model reliability
    v = pd.read_csv(o / "validation_metrics.csv")
    D["validation"] = rows(v)
    D["meta"]["plots"] = int(v.plots.max())
    wf = o / "walk_forward" / "scores_by_model.csv"
    if wf.exists():
        D["walk_forward"] = rows(pd.read_csv(wf))
        ws = o / "walk_forward" / "scores_by_season.csv"
        if ws.exists():
            D["walk_forward_season"] = rows(pd.read_csv(ws))
    mf = o / "model_features.json"
    if mf.exists():
        D["meta"]["engine"] = json.load(open(mf)).get("engine", "")

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("window.DASH = " + json.dumps(D, separators=(",", ":"), allow_nan=False) + ";\n")
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.2f} MB): trend {len(D['trend']['rows'])} rows, "
          f"adoption {len(D['adoption']['rows'])}, scenarios {len(D['scenario']['rows'])}, "
          f"walk-forward {'yes' if 'walk_forward' in D else 'no'}")


if __name__ == "__main__":
    main()

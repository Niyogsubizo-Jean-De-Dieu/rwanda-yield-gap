"""
Rwanda yield-gap model: plot-level yield model, validation, drivers (SHAP), yield gaps and input scenarios.
Run on your own PC after build_model_dataset.py.

    python3 src/train_model.py                       # uses data/model_data/model_dataset.csv -> data/model_outputs/
    python3 src/train_model.py --quick               # faster test run (fewer trees, sample for validation)

Engine: LightGBM if installed (recommended; gives exact SHAP values):
    python3 -m pip install lightgbm              # add --user or --break-system-packages if pip refuses
otherwise scikit-learn HistGradientBoosting (drivers then from permutation importance).

What it does
  1. Trains a gradient-boosted model of log(yield) per plot and crop, from plot inputs and practices,
     plot and farmer characteristics, district soil/terrain, and seasonal satellite/climate anomalies.
     Positive (monotone) effects are imposed for improved seed, manure, inorganic fertilizer (and dose), lime
     and anti-erosion works, so scenarios cannot claim that an input lowers yield (switch off: --no-monotone).
  2. Validates three ways, each against a simple baseline (average yield of the crop in that season):
       random    plots split by survey segment (5 folds)
       district  whole districts held out (6 folds of 5 districts): does it work in unseen districts?
       temporal  trained on 2022-2024, tested on 2025: does it work in a new year?
     Scores at plot level (R2 of log yield) and at district level (survey-weighted district mean yields).
  3. Drivers: mean |SHAP| per feature, overall and per crop, grouped into management / plot & farmer /
     soil & terrain / season weather / crop & season.
  4. Scenarios on the latest survey year: what the model expects if non-adopters used inorganic fertilizer
     (at the typical dose), improved seed, manure, lime, anti-erosion works, or the package of the first three.
     Gives yield gain %, attainable yield and extra production (tonnes) per district x season x crop.
  5. Fertilizer dose-response per crop.

Outputs (data/model_outputs/)
  validation_metrics.csv, model_report.txt, feature_importance.csv, importance_by_crop.csv, driver_groups.csv,
  scenario_district.csv, scenario_national.csv, top_targets.csv, dose_response.csv,
  oof_predictions.csv (district hold-out predictions), yield_model.pkl, model_features.json
These are district-level / aggregated results and can be published (no raw microdata).
"""
import argparse
import json
import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

try:
    import lightgbm as lgb
    HAVE_LGB, LGB_ERROR = True, ""
except Exception as e:          # not installed, or installed but cannot load (e.g. missing libgomp)
    HAVE_LGB, LGB_ERROR = False, f"{type(e).__name__}: {e}"
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

CAT = ["crop", "season", "stratum", "farmer_sex"]
MGMT = ["improved_seed", "organic_fert", "inorganic_fert", "inorganic_kg_ha", "lime", "micronutrient", "pesticide",
        "erosion_degree", "anti_erosion", "consolidated_site", "mechanized", "irrigated"]
PLOT = ["log_plot_area", "crop_share", "farmer_age"]
SOIL = ["soil_ph", "soil_org_carbon_gkg", "soil_nitrogen_gkg", "elevation_m", "slope_deg", "share_slope_gt16deg",
        "cropland_ha"]
WEATHER = ["ndvi_anom_mean", "ndvi_anom_min", "evi_anom_mean", "rain_anom_sum", "rain_anom_min", "lst_anom_mean",
           "lst_anom_max", "sm_anom_mean", "t2m_anom_mean", "s1_vh_anom_mean", "ndvi_anom_early", "rain_anom_early",
           "ndvi_anom_late", "rain_anom_late", "rain_total_mm", "ndvi_max"]
GROUPS = {"Management (inputs & practices)": MGMT, "Plot & farmer": PLOT + ["stratum", "farmer_sex"],
          "Soil & terrain": SOIL, "Season weather (satellite)": WEATHER, "Crop & season": ["crop", "season"]}
MONOTONE_UP = ["improved_seed", "organic_fert", "inorganic_fert", "inorganic_kg_ha", "lime", "anti_erosion"]
SCENARIOS = {
    "fertilizer": {"inorganic_fert": 1},
    "improved_seed": {"improved_seed": 1},
    "manure": {"organic_fert": 1},
    "lime": {"lime": 1},
    "anti_erosion": {"anti_erosion": 1},
    "package_fert_seed_manure": {"inorganic_fert": 1, "improved_seed": 1, "organic_fert": 1},
}
MIN_EVIDENCE = 200   # plots with and without a lever (per crop) needed before its scenario is reported


# ------------------------------------------------------------------ data
def load(path, crops_excluded):
    d = pd.read_csv(path, low_memory=False)
    d = d[~d.crop.isin(crops_excluded) & d.log_yield.notna() & (d.w_area_ha > 0)].reset_index(drop=True)
    d["log_plot_area"] = np.log(d.plot_area_ha.clip(lower=1e-4))
    for c in CAT:
        d[c] = d[c].fillna("NA").astype(str).str.strip()
    feats = [f for f in CAT + MGMT + PLOT + SOIL + WEATHER if f in d.columns]
    return d, feats


class Model:
    """Same interface for LightGBM and scikit-learn HistGradientBoosting."""

    def __init__(self, feats, cats, monotone=True, quick=False):
        self.feats, self.cats = feats, {c: sorted(cats[c]) for c in CAT if c in feats}
        self.mono = [1 if (monotone and f in MONOTONE_UP) else 0 for f in feats]
        self.n = 300 if quick else 900
        self.engine = "LightGBM" if HAVE_LGB else "scikit-learn HistGradientBoosting"

    def X(self, d):
        X = d[self.feats].copy()
        for c, levels in self.cats.items():
            X[c] = pd.Categorical(X[c], categories=levels)
            if not HAVE_LGB:
                X[c] = X[c].cat.codes.replace(-1, np.nan).astype(float)
        return X

    def fit(self, d):
        # drop columns with no information in this training set (newer scikit-learn fails on all-empty columns)
        keep = [f for f in self.feats if d[f].nunique(dropna=True) >= 2]
        if len(keep) < len(self.feats):
            self.mono = [m for f, m in zip(self.feats, self.mono) if f in keep]
            self.feats = keep
            self.cats = {c: v for c, v in self.cats.items() if c in keep}
        X, y = self.X(d), d.log_yield.values
        if HAVE_LGB:
            self.m = lgb.LGBMRegressor(n_estimators=self.n, learning_rate=0.04, num_leaves=63, min_child_samples=40,
                                       subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                                       monotone_constraints=self.mono, monotone_constraints_method="advanced",
                                       verbose=-1, random_state=1)
        else:
            self.m = HistGradientBoostingRegressor(
                max_iter=self.n, learning_rate=0.06, max_leaf_nodes=63, min_samples_leaf=40, l2_regularization=1.0,
                categorical_features=[f in self.cats for f in self.feats], monotonic_cst=self.mono,
                early_stopping=False, random_state=1)
        self.m.fit(X, y)
        self.smear = float(np.mean(np.exp(y - self.m.predict(X))))     # back-transform bias correction
        return self

    def predict(self, d):
        return self.m.predict(self.X(d))

    def contributions(self, d):
        """SHAP values (LightGBM only): rows x features."""
        return self.m.predict(self.X(d), pred_contrib=True)[:, :-1]


# ------------------------------------------------------------------ validation
def r2(y, p):
    return 1 - np.sum((y - p) ** 2) / np.sum((y - np.mean(y)) ** 2)


def district_level(d, pred_col, min_plots=20):
    """Survey-weighted district mean yield: observed vs predicted (district x year x season x crop)."""
    t = d.assign(obs=d.yield_kg_ha * d.w_area_ha, prd=d[pred_col] * d.w_area_ha)
    g = t.groupby(["district", "year", "season", "crop"]).agg(n=("obs", "size"), obs=("obs", "sum"),
                                                                prd=("prd", "sum"), w=("w_area_ha", "sum"))
    g = g[g.n >= min_plots]
    return g.obs / g.w, g.prd / g.w


def within_crop_scores(obs, prd):
    """District scores WITHIN each crop x season: can the model rank districts for the same crop?
    (pooled district R2 is flattered by differences between crops)."""
    t = pd.DataFrame({"o": np.log(obs), "p": np.log(prd)})
    key = [t.index.get_level_values("crop"), t.index.get_level_values("season")]
    dev = t - t.groupby(key).transform("mean")
    per = {c: np.corrcoef(g.o, g.p)[0, 1] for c, g in t.groupby(t.index.get_level_values("crop")) if len(g) >= 20}
    return {"district_R2_within_crop": r2(dev.o.values, dev.p.values),
            "district_corr_within_crop_median": float(np.median(list(per.values()))),
            **{f"corr_{c}": v for c, v in per.items()}}


def evaluate(d, feats, cats, a, log):
    splits = {
        "random (segments held out)": list(GroupKFold(5).split(d, groups=d.segment_id)),
        "district (districts held out)": list(GroupKFold(6).split(d, groups=d.district)),
        "temporal (train 2022-24, test 2025)": [(np.where(d.year < 2025)[0], np.where(d.year == 2025)[0])],
    }
    rows, oof_district = [], None
    for name, folds in splits.items():
        t0 = time.time()
        pred, base = np.full(len(d), np.nan), np.full(len(d), np.nan)
        for tr, te in folds:
            tr_d, te_d = d.iloc[tr], d.iloc[te]
            if a.quick and len(tr_d) > 60000:
                tr_d = tr_d.sample(60000, random_state=1)
            m = Model(feats, cats, not a.no_monotone, a.quick).fit(tr_d)
            pred[te] = m.predict(te_d) + np.log(m.smear)
            mean = tr_d.groupby(["crop", "season"]).log_yield.mean()
            base[te] = te_d.set_index(["crop", "season"]).index.map(mean).values
            base[te] += np.log(np.mean(np.exp(tr_d.log_yield - tr_d.set_index(["crop", "season"]).index.map(mean))))
        ok = ~np.isnan(pred)
        e = d[ok].assign(p_model=np.exp(pred[ok]), p_base=np.exp(base[ok]))
        om, pm_ = district_level(e, "p_model")
        _, pb = district_level(e, "p_base")
        rows.append({
            "validation": name, "plots": int(ok.sum()),
            "plot_R2_log_model": r2(d.log_yield.values[ok], pred[ok]),
            "plot_R2_log_baseline": r2(d.log_yield.values[ok], base[ok]),
            "plot_R2_within_crop": r2(d.log_yield.values[ok] - base[ok], pred[ok] - base[ok]),
            "district_R2_model": r2(om.values, pm_.values), "district_R2_baseline": r2(om.values, pb.values),
            "district_corr_model": np.corrcoef(om, pm_)[0, 1],
            "district_MAPE_model": float(np.mean(np.abs(pm_ / om - 1))),
            "district_MAPE_baseline": float(np.mean(np.abs(pb / om - 1))), "district_cells": len(om),
            **within_crop_scores(om, pm_)})
        if name.startswith("district"):
            oof_district = e[["year", "season", "district", "crop", "yield_kg_ha", "p_model", "w_area_ha"]]
        log.append(f"  {name}: done in {time.time() - t0:.0f}s")
    return pd.DataFrame(rows), oof_district


# ------------------------------------------------------------------ drivers
def drivers(m, d, feats, a, log):
    s = d.sample(min(len(d), 8000 if a.quick else 30000), random_state=2)
    if HAVE_LGB:
        sv = np.abs(m.contributions(s))
        imp = pd.DataFrame(sv, columns=feats, index=s.index)
        method = "mean |SHAP| (log-yield units)"
        overall = imp.mean().sort_values(ascending=False)
        by_crop = imp.groupby(s.crop.values).mean().T
    else:
        method = "permutation importance (drop in R2)"
        pi = permutation_importance(m.m, m.X(s), s.log_yield, n_repeats=3, random_state=2, n_jobs=-1)
        overall = pd.Series(pi.importances_mean, index=feats).clip(lower=0).sort_values(ascending=False)
        by_crop = {}
        for c, g in s.groupby("crop"):
            if len(g) >= 500 and c != "NA":
                pc = permutation_importance(m.m, m.X(g), g.log_yield, n_repeats=2, random_state=2, n_jobs=-1)
                by_crop[c] = pd.Series(pc.importances_mean, index=feats).clip(lower=0)
        by_crop = pd.DataFrame(by_crop)
    grp = {f: k for k, v in GROUPS.items() for f in v}
    fi = overall.rename("importance").reset_index().rename(columns={"index": "feature"})
    fi["group"], fi["method"] = fi.feature.map(grp), method
    within = fi.group != "Crop & season"
    fi["share_pct"] = np.where(within, 100 * fi.importance / fi.importance[within].sum(), np.nan)
    groups = fi[within].groupby("group").share_pct.sum().sort_values(ascending=False).reset_index()
    log.append(f"Drivers computed with {method} on {len(s):,} plots")
    return fi, by_crop.reset_index().rename(columns={"index": "feature"}), groups


# ------------------------------------------------------------------ scenarios
def scenarios(m, d, year, log):
    base = d[d.year == year].copy()
    users = d[(d.inorganic_fert == 1) & (d.inorganic_kg_ha > 0)]
    dose = users.groupby("crop").inorganic_kg_ha.median()
    base["p0"] = m.predict(base)
    # a lever is scored for a crop only if the survey has enough plots with AND without it (all years)
    ev = {c: (d.groupby("crop")[c].apply(lambda x: (x == 1).sum() >= MIN_EVIDENCE and (x == 0).sum() >= MIN_EVIDENCE))
          for c in ["inorganic_fert", "improved_seed", "organic_fert", "lime", "anti_erosion"]}
    out, skipped = [], []
    for name, change in SCENARIOS.items():
        for crop, b in base.groupby("crop"):
            ch = {k: v for k, v in change.items() if ev[k].get(crop, False)}
            if not ch:
                skipped.append(f"{name}/{crop}")
                continue
            s = b.copy()
            # only plots with a KNOWN "no" adopt; unknown (missing) answers stay as they are, because the
            # positive-effect constraint holds between known values only
            for k, v in ch.items():
                s.loc[b[k] == 0, k] = v
            if "inorganic_fert" in ch:
                target = dose.get(crop, dose.median())
                s.loc[b.inorganic_fert == 0, "inorganic_kg_ha"] = target
                low = (b.inorganic_fert == 1) & b.inorganic_kg_ha.notna()
                s.loc[low, "inorganic_kg_ha"] = np.fmax(b.loc[low, "inorganic_kg_ha"], target)
            adopter = b[list(ch)].eq(1).all(axis=1).astype(float)
            out.append(b.assign(scenario=name, ratio=np.exp(m.predict(s) - b.p0), adopter=adopter,
                                levers="+".join(ch)))
    log.append(f"Levers not scored (fewer than {MIN_EVIDENCE} plots with or without them): " + ", ".join(skipped))
    r = pd.concat(out, ignore_index=True)
    r["prod_t"] = r.yield_kg_ha * r.w_area_ha / 1000
    r["extra_t"] = r.prod_t * (r.ratio - 1)
    r["w_adopt"] = r.adopter.fillna(0) * r.w_area_ha

    def agg(g):
        return pd.Series({"levers": g.levers.iloc[0], "plots": len(g), "area_ha": g.w_area_ha.sum(),
                          "current_yield_kg_ha": g.prod_t.sum() * 1000 / g.w_area_ha.sum(),
                          "adoption_pct": 100 * g.w_adopt.sum() / g.w_area_ha.sum(),
                          "yield_gain_pct": 100 * g.extra_t.sum() / g.prod_t.sum(),
                          "current_production_t": g.prod_t.sum(), "extra_production_t": g.extra_t.sum()})
    dist = r.groupby(["scenario", "season", "district", "crop"]).apply(agg).reset_index()
    dist["attainable_yield_kg_ha"] = dist.current_yield_kg_ha * (1 + dist.yield_gain_pct / 100)
    dist.insert(0, "year", year)
    nat = r.groupby(["scenario", "season", "crop"]).apply(agg).reset_index()
    nat.insert(0, "year", year)
    small = dist[(dist.plots >= 20) & (dist.adoption_pct < 100)]
    top = (small.sort_values("extra_production_t", ascending=False)
           .groupby("scenario").head(15).reset_index(drop=True))
    log.append(f"Scenarios on {year} plots ({len(base):,}); typical fertilizer dose used (kg/ha, median of "
               f"users): " + ", ".join(f"{c} {v:.0f}" for c, v in dose.items()))
    return dist, nat, top


def dose_response(m, d, year):
    rows = []
    base = d[(d.year == year) & (d.inorganic_fert == 0)]
    for crop, g in base.groupby("crop"):
        if len(g) < 200:
            continue
        g = g.sample(min(len(g), 3000), random_state=3)
        p0 = m.predict(g)
        for kg in [0, 10, 25, 50, 75, 100, 150, 200, 300]:
            s = g.assign(inorganic_fert=1 if kg > 0 else 0, inorganic_kg_ha=float(kg))
            rows.append({"crop": crop, "kg_per_ha": kg,
                         "yield_gain_pct": 100 * (np.average(np.exp(m.predict(s) - p0), weights=g.w_area_ha) - 1)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/model_data/model_dataset.csv")
    ap.add_argument("--out", default="data/model_outputs")
    ap.add_argument("--exclude-crops", default="Paddy rice",
                    help="comma list; rice excluded by default (few plots, does not match NISR tables)")
    ap.add_argument("--no-monotone", action="store_true")
    ap.add_argument("--quick", action="store_true", help="fast test run")
    ap.add_argument("--skip-validation", action="store_true")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    log, t0 = [], time.time()

    d, feats = load(a.data, [c.strip() for c in a.exclude_crops.split(",") if c.strip()])
    cats = {c: d[c].unique() for c in CAT if c in feats}
    engine = "LightGBM" if HAVE_LGB else f"scikit-learn HistGradientBoosting (LightGBM not loaded: {LGB_ERROR})"
    log.append(f"Engine: {engine} | monotone effects: {not a.no_monotone} | {len(d):,} plots, {len(feats)} features")
    log.append(f"Crops: {', '.join(sorted(d.crop.unique()))} | years {d.year.min()}-{d.year.max()}")
    print(log[0]); print(log[1])

    if not a.skip_validation:
        print("Validating (random / district hold-out / temporal) ...")
        met, oof = evaluate(d, feats, cats, a, log)
        met.round(4).to_csv(out / "validation_metrics.csv", index=False)
        oof.to_csv(out / "oof_predictions.csv", index=False)

    print("Training final model on all data ...")
    m = Model(feats, cats, not a.no_monotone, a.quick).fit(d)
    with open(out / "yield_model.pkl", "wb") as f:
        pickle.dump(m, f)
    json.dump({"features": feats, "categories": {k: list(v) for k, v in m.cats.items()}, "engine": m.engine,
               "smearing": m.smear, "monotone_up": MONOTONE_UP if not a.no_monotone else []},
              open(out / "model_features.json", "w"), indent=1)

    print("Drivers ...")
    fi, by_crop, groups = drivers(m, d, feats, a, log)
    fi.to_csv(out / "feature_importance.csv", index=False)
    by_crop.to_csv(out / "importance_by_crop.csv", index=False)
    groups.to_csv(out / "driver_groups.csv", index=False)

    print("Scenarios ...")
    year = int(d.year.max())
    dist, nat, top = scenarios(m, d, year, log)
    dist.round(3).to_csv(out / "scenario_district.csv", index=False)
    nat.round(3).to_csv(out / "scenario_national.csv", index=False)
    top.round(3).to_csv(out / "top_targets.csv", index=False)
    dr = dose_response(m, d, year)
    dr.round(2).to_csv(out / "dose_response.csv", index=False)

    # ---------------- report
    pd.set_option("display.width", 200)
    rep = ["RWANDA YIELD-GAP MODEL - REPORT", "=" * 60] + log
    if not a.skip_validation:
        v = met.set_index("validation")
        rep += ["", "VALIDATION (model vs baseline = average yield of the crop in that season)",
                v[["plot_R2_log_model", "plot_R2_log_baseline", "plot_R2_within_crop", "district_R2_model", "district_R2_baseline",
                   "district_R2_within_crop", "district_corr_within_crop_median", "district_MAPE_model",
                   "district_MAPE_baseline", "district_cells"]].round(3).T.to_string(),
                "", "District correlation (observed vs predicted) per crop:",
                v[[c for c in v.columns if c.startswith("corr_")]].round(2).T.to_string()]
    rep += ["", "WHAT DRIVES YIELD DIFFERENCES WITHIN A CROP (share of importance, %; crop identity excluded)",
            groups.round(1).to_string(index=False),
            "", "Top 15 features", fi[fi.share_pct.notna()].head(15)[["feature", "group", "share_pct"]].round(1).to_string(index=False)]
    piv = nat.pivot_table(index=["crop", "season"], columns="scenario", values="yield_gain_pct").round(1)
    rep += ["", f"NATIONAL YIELD GAIN (%) IF NON-ADOPTERS ADOPT, {year}", piv.to_string()]
    ex = nat.pivot_table(index="crop", columns="scenario", values="extra_production_t", aggfunc="sum").round(0)
    rep += ["", f"EXTRA PRODUCTION (tonnes, seasons A+B {year})", ex.to_string()]
    t = top[top.scenario == "package_fert_seed_manure"].head(10)
    rep += ["", "TOP 10 TARGETS for the fertilizer + seed + manure package (extra tonnes)",
            t[["season", "district", "crop", "adoption_pct", "yield_gain_pct", "extra_production_t"]]
            .round(1).to_string(index=False)]
    rep += ["", "Interpretation: effects are model-based associations from survey data (not field trials). "
            "Positive effects are imposed for inputs; gains assume non-adopters respond like comparable "
            "adopters in the same conditions. Blank = lever not scored for that crop (too few plots with it).",
            "plot_R2_within_crop = share of the yield variation WITHIN a crop and season explained by the model.",
            "district_R2_within_crop = how well district yields are ranked for the SAME crop and season (the honest "
            "test for a yield-gap map; the baseline scores 0 here).", f"Run time {time.time() - t0:.0f}s"]
    (out / "model_report.txt").write_text("\n".join(rep) + "\n")
    print("\n".join(rep))
    print(f"\nDone. Outputs in {out}/")


if __name__ == "__main__":
    main()

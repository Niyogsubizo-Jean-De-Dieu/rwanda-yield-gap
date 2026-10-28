"""
Walk-forward (expanding-window) validation and model comparison for the Rwanda yield-gap project.

For every test season, all models are trained ONLY on the seasons before it, then scored on that season:
    train 2022A-2023B -> test 2024A
    train 2022A-2024A -> test 2024B
    train 2022A-2024B -> test 2025A
    train 2022A-2025A -> test 2025B
(--first-test 2023A adds earlier folds.)

Models
  Baselines (what a statistician could do without a model)
    national_mean      average yield of the crop in that season (all districts)
    district_history   the district's own past average for that crop and season
    last_year          the district's result for that crop in the same season one year earlier
  Machine learning (same 42 features as train_model.py: inputs, plot & farmer, soil & terrain, satellite)
    ridge              linear regression with L2 penalty (one-hot categories, scaled numbers)
    random_forest      scikit-learn RandomForest
    sk_gbm             scikit-learn HistGradientBoosting
    sk_gbm_district    same + district name as a feature
    lightgbm           LightGBM (if installed)
    lightgbm_district  LightGBM + district name as a feature (allowed here: test districts were seen in training)
    xgboost, catboost  if installed
    ensemble           average of the tree models (log scale)
    hybrid             district history x season anomaly from the gradient-boosting model:
                       the model only says how THIS season differs from the district's normal

This is an END-OF-SEASON estimate: each test season's own inputs and satellite anomalies are used. It tests
whether the model can estimate district yields for a season it has never seen (support/replace survey
estimates), not a pre-planting forecast.

Run (after build_model_dataset.py):
    python3 src/compare_models.py                 # ~10-20 min
    python3 src/compare_models.py --quick         # ~3 min test
Outputs (data/model_outputs/walk_forward/): scores_by_model.csv, scores_by_season.csv, scores_by_crop.csv,
    district_predictions.csv, walk_forward_report.txt
"""
import argparse
import warnings
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import train_model as tm  # noqa: E402

try:
    import xgboost as xgb
except Exception:
    xgb = None
try:
    import catboost as cb
except Exception:
    cb = None

SEASONS = [f"{y}{s}" for y in range(2022, 2026) for s in "AB"]
CELL = ["district", "crop", "season"]
warnings.filterwarnings("ignore", category=RuntimeWarning)
TREE_MODELS = ["random_forest", "sk_gbm", "lightgbm", "xgboost", "catboost"]


# ------------------------------------------------------------------ helpers
def season_key(d):
    return d.year.astype(str) + d.season


def smear(y, p):
    return float(np.mean(np.exp(y - p)))


def num_cat(feats):
    cats = [f for f in feats if f in tm.CAT or f == "district"]
    return [f for f in feats if f not in cats], cats


# ------------------------------------------------------------------ baselines
# Computed the way a statistician would: survey-weighted (area) mean yields in kg/ha, no model.
def _wmean(t, keys):
    g = t.assign(p=t.yield_kg_ha * t.w_area_ha).groupby(keys)
    return pd.DataFrame({"y": g.p.sum() / g.w_area_ha.sum(), "n": g.size()})


def baseline_national(tr, te):
    nat = _wmean(tr, ["crop", "season"]).y
    return np.log(te.set_index(["crop", "season"]).index.map(nat).to_numpy(float))


def _shrunk(src, te, prior, k):
    g = _wmean(src, CELL)
    key = te.set_index(CELL).index
    n = np.nan_to_num(key.map(g.n).to_numpy(float))
    y = np.nan_to_num(key.map(g.y).to_numpy(float))
    return np.where(n > 0, (n * y + k * prior) / (n + k), prior)


def baseline_district_history(tr, te, k=30):
    """District's own past mean yield for that crop and season (shrunk to national when few plots)."""
    prior = np.exp(baseline_national(tr, te))
    return np.log(_shrunk(tr, te, prior, k))


def baseline_last_year(tr, te, k=30):
    """District's yield for the crop in the same season one year earlier (shrunk to its history)."""
    prev = tr[tr.year == te.year.iloc[0] - 1]
    prior = np.exp(baseline_district_history(tr, te, k))
    if prev.empty:
        return np.log(prior)
    return np.log(_shrunk(prev, te, prior, k))


def hybrid(tr, te, p_tr, p_te, p_hist):
    """District history x (model's yield for this season / model's yield for the district's past seasons).
    The model only supplies how THIS season differs from the district normal (weather, inputs)."""
    def cell_mean(t, p):
        w = t.w_area_ha.to_numpy()
        a = pd.DataFrame({"pw": np.exp(p) * w, "w": w}, index=pd.MultiIndex.from_frame(t[CELL]))
        g = a.groupby(level=CELL).sum()
        return g.pw / g.w
    key = te.set_index(CELL).index
    now = key.map(cell_mean(te, p_te)).to_numpy(float)
    past = key.map(cell_mean(tr, p_tr)).to_numpy(float)
    ratio = np.where(np.isfinite(now / past), now / past, 1.0)
    return p_hist + np.log(ratio)


# ------------------------------------------------------------------ ML models
def make_frame(d, feats, levels):
    X = d[feats].copy()
    for c in levels:
        X[c] = pd.Categorical(X[c].astype(str), categories=levels[c])
    return X


def fit_predict(name, tr, te, feats, quick):
    # drop columns with no information in the training seasons (e.g. 'mechanized' is only asked from 2024)
    feats = [f for f in feats if tr[f].nunique(dropna=True) >= 2]
    num, cat = num_cat(feats)
    levels = {c: sorted(pd.concat([tr[c], te[c]]).astype(str).unique()) for c in cat}
    y = tr.log_yield.to_numpy()
    n_trees = 250 if quick else 700
    if name == "ridge":
        pre = ColumnTransformer([
            ("num", make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler()), num),
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20), cat)])
        m = make_pipeline(pre, Ridge(alpha=10.0))
        m.fit(tr[feats], y)
        f = lambda d: m.predict(d[feats])
    elif name in ("random_forest", "sk_gbm"):
        def enc(d):
            X = make_frame(d, feats, levels)
            for c in cat:
                X[c] = X[c].cat.codes.replace(-1, np.nan).astype(float)
            return X
        if name == "random_forest":
            Xt = enc(tr)
            Xt = Xt.fillna(-999)          # RF in older scikit-learn has no NaN support
            m = RandomForestRegressor(n_estimators=120 if quick else 300, min_samples_leaf=20, max_features=0.33,
                                      max_samples=min(len(tr), 60000), n_jobs=-1, random_state=1)
            m.fit(Xt, y)
            f = lambda d: m.predict(enc(d).fillna(-999))
        else:
            m = HistGradientBoostingRegressor(max_iter=n_trees, learning_rate=0.05, max_leaf_nodes=63,
                                              min_samples_leaf=40, l2_regularization=1.0, random_state=1,
                                              categorical_features=[c in cat for c in feats], early_stopping=False)
            m.fit(enc(tr), y)
            f = lambda d: m.predict(enc(d))
    elif name.startswith("lightgbm"):
        m = tm.lgb.LGBMRegressor(n_estimators=n_trees, learning_rate=0.04, num_leaves=63, min_child_samples=40,
                                 subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                                 verbose=-1, random_state=1)
        m.fit(make_frame(tr, feats, levels), y)
        f = lambda d: m.predict(make_frame(d, feats, levels))
    elif name == "xgboost":
        m = xgb.XGBRegressor(n_estimators=n_trees, learning_rate=0.05, max_depth=7, min_child_weight=20,
                             subsample=0.8, colsample_bytree=0.8, tree_method="hist", enable_categorical=True,
                             random_state=1, n_jobs=-1)
        m.fit(make_frame(tr, feats, levels), y)
        f = lambda d: m.predict(make_frame(d, feats, levels))
    elif name == "catboost":
        def cbx(d):
            X = d[feats].copy()
            for c in cat:
                X[c] = X[c].astype(str)
            return X
        m = cb.CatBoostRegressor(iterations=n_trees, learning_rate=0.06, depth=7, verbose=0, random_seed=1,
                                 cat_features=cat)
        m.fit(cbx(tr), y)
        f = lambda d: m.predict(cbx(d))
    else:
        raise ValueError(name)
    ptr = f(tr)
    c = np.log(smear(y, ptr))
    return f(te) + c, ptr + c


# ------------------------------------------------------------------ scoring
def district_cells(te, preds, min_plots):
    """Survey-weighted district x crop yields: observed and each model's prediction."""
    t = te[CELL + ["year", "w_area_ha", "yield_kg_ha"]].copy()
    w = t.w_area_ha
    agg = {"obs": (t.yield_kg_ha * w)}
    for k, p in preds.items():
        agg[k] = np.exp(p) * w
    a = pd.DataFrame(agg).assign(w=w, n=1)
    for c in CELL + ["year"]:
        a[c] = t[c].values
    g = a.groupby(CELL + ["year"]).sum(numeric_only=True)
    g = g[g.n >= min_plots]
    out = g[["obs"] + list(preds)].div(g.w, axis=0)
    out["n_plots"] = g.n
    return out.reset_index()


def score(cells, models, by=None):
    rows = []
    groups = cells.groupby(by) if by else [("all", cells)]
    for key, g in groups:
        lo = np.log(g.obs)
        dev_o = lo - lo.groupby([g.crop, g.season, g.year]).transform("mean")
        for m in models:
            lp = np.log(g[m])
            dev_p = lp - lp.groupby([g.crop, g.season, g.year]).transform("mean")
            per_crop = [np.corrcoef(np.log(x.obs), np.log(x[m]))[0, 1] for _, x in g.groupby(["crop", "season", "year"])
                        if len(x) >= 8]
            rows.append({**({"group": key} if by else {}), "model": m, "cells": len(g),
                         "MAPE_%": 100 * float(np.mean(np.abs(g[m] / g.obs - 1))),
                         "R2_within_crop": tm.r2(dev_o.values, dev_p.values),
                         "median_corr_within_crop": float(np.nanmedian(per_crop)) if per_crop else np.nan,
                         "bias_%": 100 * float(np.median(g[m] / g.obs - 1))})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ main
def run(data, out, first_test="2024A", quick=False, min_plots=20, exclude=("Paddy rice",), log=print):
    d, feats = tm.load(data, list(exclude))
    d["sk"] = season_key(d)
    models = ["national_mean", "district_history", "last_year", "ridge", "random_forest", "sk_gbm", "sk_gbm_district"]
    if tm.HAVE_LGB:
        models += ["lightgbm", "lightgbm_district"]
    if xgb is not None:
        models.append("xgboost")
    if cb is not None:
        models.append("catboost")
    trees = [m for m in models if m in TREE_MODELS]
    log(f"Models: {', '.join(models)} + ensemble({', '.join(trees)}) + hybrid (district history x GBM season anomaly)")
    tests = [s for s in SEASONS if s >= first_test and s in set(d.sk)]
    cells, plot_rows = [], []
    for s in tests:
        t0 = time.time()
        tr, te = d[d.sk < s].reset_index(drop=True), d[d.sk == s].reset_index(drop=True)
        preds = {"national_mean": baseline_national(tr, te), "district_history": baseline_district_history(tr, te),
                 "last_year": baseline_last_year(tr, te)}
        train_preds = {}
        for m in models[3:]:
            f = feats + ["district"] if m.endswith("_district") else feats
            preds[m], train_preds[m] = fit_predict(m.replace("_district", ""), tr, te, f, quick)
        # hybrid: district normal (history) x season anomaly estimated by the ML model
        gbm = "lightgbm" if "lightgbm" in preds else "sk_gbm"
        preds["hybrid"] = hybrid(tr, te, train_preds[gbm], preds[gbm], preds["district_history"])
        preds["ensemble"] = np.mean([preds[m] for m in trees], axis=0)
        for m, p in preds.items():
            ok = ~np.isnan(p)
            plot_rows.append({"test_season": s, "model": m,
                              "plot_R2_log": tm.r2(te.log_yield.values[ok], p[ok])})
        c = district_cells(te, preds, min_plots)
        c.insert(0, "test_season", s)
        cells.append(c)
        log(f"  test {s}: trained on {tr.sk.nunique()} seasons ({len(tr):,} plots), tested on {len(te):,} plots, "
            f"{len(c)} district-crop cells  [{time.time() - t0:.0f}s]")
    cells = pd.concat(cells, ignore_index=True)
    names = models + ["ensemble", "hybrid"]
    overall = score(cells, names).merge(
        pd.DataFrame(plot_rows).groupby("model").plot_R2_log.mean().reset_index(), on="model")
    overall = overall.sort_values("MAPE_%").reset_index(drop=True)
    by_season = score(cells, names, by="test_season")
    by_crop = score(cells, names, by="crop")
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    overall.round(4).to_csv(out / "scores_by_model.csv", index=False)
    by_season.round(4).to_csv(out / "scores_by_season.csv", index=False)
    by_crop.round(4).to_csv(out / "scores_by_crop.csv", index=False)
    cells.round(2).to_csv(out / "district_predictions.csv", index=False)
    return overall, by_season, by_crop, cells


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/model_data/model_dataset.csv")
    ap.add_argument("--out", default="data/model_outputs/walk_forward")
    ap.add_argument("--first-test", default="2024A", help="first test season, e.g. 2023A or 2024A")
    ap.add_argument("--min-plots", type=int, default=20, help="plots needed for a district-crop cell")
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    lines = []
    log = lambda s: (print(s), lines.append(s))
    t0 = time.time()
    overall, by_season, by_crop, cells = run(a.data, a.out, a.first_test, a.quick, a.min_plots, log=log)
    pd.set_option("display.width", 220)
    best = overall.iloc[0].model
    piv = lambda t, v: t.pivot(index="model", columns="group", values=v).loc[overall.model].round(1)
    rep = ["", "WALK-FORWARD VALIDATION (each season predicted by models trained only on earlier seasons)",
           "District x crop cells, survey-weighted; MAPE = mean absolute % error of district yield;",
           "R2_within_crop = how well districts are ranked for the same crop and season.", "",
           overall.round(3).to_string(index=False),
           "", "MAPE (%) by test season", piv(by_season, "MAPE_%").to_string(),
           "", "R2 within crop by test season", by_season.pivot(index="model", columns="group",
                                                               values="R2_within_crop").loc[overall.model].round(2).to_string(),
           "", "MAPE (%) by crop", piv(by_crop, "MAPE_%").to_string(),
           "", f"Best model by MAPE: {best}. Run time {time.time() - t0:.0f}s"]
    print("\n".join(rep))
    (Path(a.out) / "walk_forward_report.txt").write_text("\n".join(lines + rep) + "\n")


if __name__ == "__main__":
    main()

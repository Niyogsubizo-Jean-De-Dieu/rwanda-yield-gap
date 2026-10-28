"""
Build the final model dataset for the Rwanda yield-gap project (run on your own PC).

It combines
  1. NISR Seasonal Agricultural Survey microdata 2022-2025 (plot level), via prepare_microdata.py
  2. District soil and terrain (iSDAsoil, SRTM) from the Earth Engine export static_district_features.csv
  3. Seasonal satellite and climate anomalies per district (NDVI, EVI, rainfall, temperature, soil moisture,
     radar) from the Earth Engine exports timeseries_<year>.csv

Folder layout (run from the repository root):
  src/prepare_microdata.py, src/build_model_dataset.py
  data/sas_district_yield_panel.csv          (check against NISR published yields)
  data/microdata/2022 ... 2025/              (unzipped NISR downloads, as they are; not on GitHub)
  data/gee_exports/static_district_features.csv, cropland_area.csv, timeseries_2017.csv ... timeseries_2026.csv

Run
  python3 src/build_model_dataset.py
  python3 src/build_model_dataset.py --microdata data/microdata --gee data/gee_exports --out data/model_data

Outputs (in data/model_data/)
  plot_crop_dataset.csv        all crop records, all years (from prepare_microdata.py)
  district_crop_summary.csv    survey-weighted adoption rates and yields by district x crop x season
  model_dataset.csv            FINAL: smallholder plots of the main crops with a usable yield, plus district
                               soil/terrain and seasonal satellite anomalies, ready for the models
  model_dataset_report.txt     rows by year/season/crop, missing values, data checks
  data_dictionary.csv          meaning of every column
"""
import argparse
import glob
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_microdata as pm  # noqa: E402

MAIN_CROPS = ["Maize", "Bush bean", "Climbing bean", "Irish potato", "Sweet potato", "Cassava", "Sorghum",
              "Paddy rice", "Soybean", "Wheat"]
DYN = ["ndvi", "evi", "lst_day_c", "rain_mm", "soil_moisture", "t2m_c", "s1_vv_db", "s1_vh_db"]
STATIC = ["soil_ph", "soil_org_carbon_gkg", "soil_nitrogen_gkg", "elevation_m", "slope_deg", "share_slope_gt16deg"]
MODEL_COLS = [
    # identifiers
    "year", "season", "district", "province", "segment_id", "plot_no", "crop", "crop_category",
    # target
    "yield_kg_ha", "log_yield", "share_imputed",
    # inputs and practices (plot level)
    "improved_seed", "organic_fert", "inorganic_fert", "inorganic_kg_ha", "lime", "micronutrient", "pesticide",
    "erosion_degree", "anti_erosion", "consolidated_site", "mechanized", "irrigated",
    # plot and farmer
    "plot_area_ha", "crop_area_ha", "crop_share", "farmer_sex", "farmer_age", "stratum",
    # survey design
    "weight", "w_area_ha",
]
EXTRA_DICT = {
    "log_yield": "Natural log of yield (model target)",
    "crop_share": "Share of the plot under this crop (crop_area_ha / plot_area_ha)",
    "soil_ph": "Soil pH, 0-20 cm, mean over district cropland (iSDAsoil)",
    "soil_org_carbon_gkg": "Soil organic carbon g/kg, 0-20 cm (iSDAsoil)",
    "soil_nitrogen_gkg": "Soil total nitrogen g/kg, 0-20 cm (iSDAsoil)",
    "elevation_m": "Mean elevation of district cropland (SRTM)", "slope_deg": "Mean slope of district cropland",
    "share_slope_gt16deg": "Share of district cropland on slopes > 16 degrees",
    "cropland_ha": "District cropland area from the consensus satellite cropland mask",
}


def norm(s):
    return re.sub(r"[^a-z]", "", str(s).lower())


# ------------------------------------------------------------------ satellite features
def find_gee_dir(gee_dir):
    """Folder holding static_district_features.csv: gee_dir, any subfolder of it, or gee_exports.zip unpacked."""
    gee = Path(gee_dir)
    for z in [gee.with_suffix(".zip"), Path("gee_exports.zip"), *gee.glob("*.zip")]:
        if z.exists() and not any(gee.rglob("static_district_features.csv")):
            import zipfile
            zipfile.ZipFile(z).extractall(gee)
            print(f"Unzipped {z} into {gee}/")
    hits = sorted(gee.rglob("static_district_features.csv")) if gee.exists() else []
    return hits[0].parent if hits else gee


def load_gee(gee_dir, log):
    gee = find_gee_dir(gee_dir)
    static_path = gee / "static_district_features.csv"
    ts_files = sorted(glob.glob(str(gee / "timeseries_*.csv")))
    if not static_path.exists() or not ts_files:
        log.append(f"Satellite features: NOT FOUND. Put static_district_features.csv, cropland_area.csv and "
                   f"timeseries_2017..2026.csv (or gee_exports.zip) in '{gee_dir}/' -> built without them")
        return None, None
    log.append(f"Satellite files read from {gee}/ ({len(ts_files)} time-series files)")
    static = pd.read_csv(static_path).drop(columns=["system:index", ".geo"], errors="ignore")
    static["dkey"] = static.district_gaul.map(norm)
    area = gee / "cropland_area.csv"
    if area.exists():
        a = pd.read_csv(area).rename(columns={"sum": "cropland_ha"})
        a["dkey"] = a.district_gaul.map(norm)
        static = static.merge(a[["dkey", "cropland_ha"]], on="dkey", how="left")
    static = static[["dkey"] + [c for c in STATIC + ["cropland_ha"] if c in static.columns]]

    seq = pd.concat([pd.read_csv(f) for f in ts_files], ignore_index=True)
    seq["dkey"] = seq.district_gaul.map(norm)
    for c in DYN:
        if c not in seq:
            seq[c] = np.nan
    # anomaly = value minus the district's average for the same 16-day period of the season (all years)
    clim = seq.groupby(["dkey", "season", "period"])[DYN].transform("mean")
    an = seq[["dkey", "year", "season", "period"]].join(seq[DYN] - clim)
    g = an.groupby(["dkey", "year", "season"])
    f = pd.DataFrame({
        "ndvi_anom_mean": g.ndvi.mean(), "ndvi_anom_min": g.ndvi.min(), "evi_anom_mean": g.evi.mean(),
        "rain_anom_sum": g.rain_mm.sum(), "rain_anom_min": g.rain_mm.min(),
        "lst_anom_mean": g.lst_day_c.mean(), "lst_anom_max": g.lst_day_c.max(),
        "sm_anom_mean": g.soil_moisture.mean(), "t2m_anom_mean": g.t2m_c.mean(),
        "s1_vh_anom_mean": g.s1_vh_db.mean()})
    for half, (lo, hi) in {"early": (1, 5), "late": (6, 11)}.items():
        h = an[an.period.between(lo, hi)].groupby(["dkey", "year", "season"])
        f[f"ndvi_anom_{half}"] = h.ndvi.mean()
        f[f"rain_anom_{half}"] = h.rain_mm.sum()
    # absolute seasonal climate (district character, not anomaly)
    r = seq.groupby(["dkey", "year", "season"])
    f["rain_total_mm"] = r.rain_mm.sum()
    f["ndvi_max"] = r.ndvi.max()
    f = f.reset_index()
    log.append(f"Satellite features: {len(static)} districts static; anomalies for "
               f"{f[['year', 'season']].drop_duplicates().shape[0]} seasons ({f.year.min()}-{f.year.max()})")
    return static, f


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--microdata", default="data/microdata")
    ap.add_argument("--gee", default="data/gee_exports")
    ap.add_argument("--panel", default="data/sas_district_yield_panel.csv",
                    help="NISR published district yields, for the validation check (optional)")
    ap.add_argument("--out", default="data/model_data")
    ap.add_argument("--seasons", default="A,B")
    ap.add_argument("--use-imputed-shares", action="store_true",
                    help="also use 2024 B yields whose crop share was imputed (mixed plots); default off")
    ap.add_argument("--crops", default=",".join(MAIN_CROPS))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    log = []

    # 1. survey microdata -> plot_crop_dataset
    files = list(pm.find_files(a.microdata, tuple(x.strip().upper() for x in a.seasons.split(","))))
    if not files:
        sys.exit(f"No SAS production files found under '{a.microdata}/'. Check the folder name.")
    print(f"Reading {len(files)} survey seasons ...")
    pm.USE_IMPUTED_SHARES = a.use_imputed_shares
    pm.build_share_reference(files, log)
    parts = [x for x in (pm.prepare_one(y, s, pp, fp, log, sp) for y, s, pp, fp, sp in files) if x is not None]
    plots = pd.concat(parts, ignore_index=True)[pm.KEEP]
    plots.to_csv(out / "plot_crop_dataset.csv", index=False)
    summ = pm.district_summary(plots)
    summ.to_csv(out / "district_crop_summary.csv", index=False)
    if Path(a.panel).exists():
        pm.validate(summ, a.panel, log)
    else:
        log.append(f"(validation skipped: {a.panel} not found)")

    # 2. model dataset: smallholders, main crops, usable and non-extreme yields
    crops = [c.strip() for c in a.crops.split(",")]
    d = plots[(plots.is_lsf == 0) & (plots.usable_yield == 1) & (plots.extreme_yield == 0)
              & plots.crop.isin(crops)].copy()
    d["log_yield"] = np.log(d.yield_kg_ha)
    d["crop_share"] = (d.crop_area_ha / d.plot_area_ha).clip(upper=1)
    d = d[MODEL_COLS]
    d["dkey"] = d.district.map(norm)

    # 3. add satellite and soil context
    static, anom = load_gee(a.gee, log)
    if static is not None:
        n0 = len(d)
        d = d.merge(static, on="dkey", how="left").merge(anom, on=["dkey", "year", "season"], how="left")
        unmatched = sorted(d.loc[d[STATIC[0]].isna(), "district"].unique())
        if unmatched:
            log.append(f"WARNING districts without satellite match: {unmatched}")
        log.append(f"Satellite context joined to {d[STATIC[0]].notna().mean():.0%} of rows (soil) and "
                   f"{d['ndvi_anom_mean'].notna().mean():.0%} (seasonal anomalies); rows unchanged: {len(d) == n0}")
    d = d.drop(columns="dkey")
    d.to_csv(out / "model_dataset.csv", index=False)

    # 4. report + dictionary
    counts = d.pivot_table(index=["year", "season"], columns="crop", values="yield_kg_ha", aggfunc="size",
                           fill_value=0)
    miss = d.isna().mean().round(3)
    log.append(f"\nFINAL model_dataset.csv: {len(d):,} rows x {d.shape[1]} columns")
    log.append("\nRows by season and crop:\n" + counts.to_string())
    log.append("\nShare missing per column (only columns with any missing):\n" + miss[miss > 0].to_string())
    (out / "model_dataset_report.txt").write_text("\n".join(log) + "\n")
    dic = {**pm.DICTIONARY, **EXTRA_DICT}
    pd.DataFrame([{"column": c, "meaning": dic.get(c, "Seasonal satellite/climate anomaly vs district average "
                   "(same 16-day periods)" if "anom" in c else "")} for c in d.columns]
                 ).to_csv(out / "data_dictionary.csv", index=False)
    print("\n".join(log))
    print(f"\nDone. Final dataset: {out / 'model_dataset.csv'}")


if __name__ == "__main__":
    main()

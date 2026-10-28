"""
Prepare NISR Seasonal Agricultural Survey (SAS) microdata (2022-2025) into one analysis-ready table.

Folder layout: one folder per year, unzipped as downloaded from microdata.statistics.gov.rw.
All NISR layouts are found automatically (CSV preferred, Stata .dta otherwise):
    microdata/2025/Season A/Rwa_raw_SeasonA2025_Production.csv   (+ Rwa_raw_fertilizer_pesticideA2025.csv)
    microdata/2024/Season A/Rwa_raw_SeasonA2024_Production.csv   (+ fertilizer_pesticideA2024.csv + SeasonA2024_Screening.csv)
    microdata/2023/CSV files/rwa-sas-seasonA_Crop production.csv  (+ ..._PartIII_Fertilizers_Pesticides.csv)
    microdata/2022/STATA/rwa-sas-seasonA_Crop production.dta      (+ ..._PartIII_Fertilizers_Pesticides.dta)
The season is read from the file name, so a misfiled file is still matched correctly.

Usage
    python3 src/prepare_microdata.py --in microdata --out model_data          # build the dataset
    python3 src/prepare_microdata.py --in microdata --inspect                 # list files + columns
    python3 src/prepare_microdata.py --in microdata --out model_data --validate sas_district_yield_panel.csv

Outputs (in --out)
    plot_crop_dataset.csv      one row per crop on a surveyed plot
    district_crop_summary.csv  survey-weighted adoption rates and yields per year x season x district x crop
    data_quality_report.txt    what was read, matched, flagged, and (with --validate) the check against
                               NISR's published district yields
    data_dictionary.csv        meaning of every output column
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ------------------------------------------------------------------ year settings
# Production-file columns. None = not in that year's production file (taken from the fertilizer file
# when possible). "plot_area_m2" + "crop_share_pct" are used when area columns in ha are absent.
PROD = {
    2025: dict(yield_kg_ha="Yield", harvested_area_ha="Harvested_Crop_Area_ha", plot_area_ha="Plot_area_ha",
               crop_area_ha="Crop_Area_ha", plot_area_m2="s2q2", crop_share_pct=None,
               organic_any="s3q1", organic_plot="s3q3", inorganic_any="s3q7", inorganic_plot="s3q9",
               micronutrient_plot="s3q17", pesticide_any="s3q18", pesticide_plot="s3q19",
               erosion_degree="s4q1", anti_erosion_plot="s4q3", consolidated_site="s4q6",
               mechanized_plot="s4q9", irrigated_plot="s4q14"),
    2024: dict(yield_kg_ha=None, harvested_area_ha=None, plot_area_ha=None, crop_area_ha=None,
               plot_area_m2="s2q2", crop_share_pct=None,
               organic_any="s3q1", organic_plot="s3q3", inorganic_any="s3q7", inorganic_plot="s3q9",
               micronutrient_plot="s3q17", pesticide_any="s3q18", pesticide_plot="s3q19",
               erosion_degree="s4q1", anti_erosion_plot="s4q3", consolidated_site="s4q6",
               mechanized_plot="s4q9", irrigated_plot="s4q14",
               # no yield/area columns in 2024: yield = harvest kg (s2q21) / (plot area x crop share from the
               # screening file). Exact for seasonal crops when tested on 2025; perennials need NISR's harvest
               # ratio (not public), so their 2024 yields are left blank.
               harvest_kg="s2q21", crop_share_from_screening=True),
    2023: dict(yield_kg_ha="yield", harvested_area_ha="Harv_area", plot_area_ha=None, crop_area_ha=None,
               plot_area_m2="s2q2", crop_share_pct="s3q2_1",
               organic_any=None, organic_plot="s3q3", inorganic_any=None, inorganic_plot="s3q9",
               micronutrient_plot="s3q17", pesticide_any=None, pesticide_plot="s3q19",
               erosion_degree="s4q1", anti_erosion_plot="s4q3", consolidated_site="s4q6",
               mechanized_plot=None, irrigated_plot="s4q15"),
    2022: dict(yield_kg_ha="yield", harvested_area_ha="Harv_area", plot_area_ha=None, crop_area_ha=None,
               plot_area_m2="s2q2", crop_share_pct="s3q2_1",
               organic_any=None, organic_plot=None, inorganic_any=None, inorganic_plot=None,
               micronutrient_plot=None, pesticide_any=None, pesticide_plot=None,
               erosion_degree=None, anti_erosion_plot=None, consolidated_site=None,
               mechanized_plot=None, irrigated_plot=None),
}
COMMON = dict(segment_id="Segment_ID", province="s1q1", district="s1q2", stratum="s1q3", farmer_type="s1q7",
              farmer_sex="s1q8", farmer_age="s1q9", plot_no="s2q1", crop="s2q4", crop_category="CropCategory",
              seed_type="s2q11", weight="plot_weight")
# Fertilizer-file questions are numbered the same in 2022-2025
FERT_FLAGS = dict(organic_any="s3q1", organic_plot="s3q3", inorganic_any="s3q7", inorganic_plot="s3q9",
                  micronutrient_plot="s3q17", pesticide_any="s3q18", pesticide_plot="s3q19")
LIME_WORDS = ("lime", "chaux", "ishwagara")
EXT_RANK = {".csv": 0, ".dta": 1}          # .sav needs pyreadstat, so CSV/Stata are used
YES = {"yes", "1", "1.0", "y"}
NO = {"no", "2", "2.0", "n"}
EROSION = {"very low": 0, "low": 1, "moderate": 2, "severe": 3}

DICTIONARY = {
    "year": "Survey year (NISR agricultural-year label)", "season": "A (Sep-Feb) or B (Mar-Jun)",
    "segment_id": "Survey segment (area-frame unit; location not public)", "province": "Province",
    "district": "District", "stratum": "Sampling stratum", "is_lsf": "1 = large-scale farm",
    "farmer_type": "Small/large scale, individual or cooperative", "farmer_sex": "Sex of farmer",
    "farmer_age": "Age of farmer (years)", "plot_no": "Plot number within segment", "crop": "Crop name",
    "crop_category": "NISR crop group", "improved_seed": "1 = improved seed sown",
    "organic_fert": "1 = manure/compost on this plot", "inorganic_fert": "1 = inorganic fertilizer on this plot",
    "inorganic_kg_ha": "Inorganic fertilizer, kg per ha of plot (kg-unit records)", "lime": "1 = lime applied",
    "micronutrient": "1 = micronutrients on this plot", "pesticide": "1 = pesticide/fungicide on this plot",
    "erosion_degree": "Erosion on plot: 0 very low .. 3 severe (2023+)",
    "anti_erosion": "1 = anti-erosion works (2023+)", "consolidated_site": "1 = land-consolidation site (2023+)",
    "mechanized": "1 = mechanical equipment (2024+)", "irrigated": "1 = plot irrigated (2023+)",
    "plot_area_ha": "Plot area (ha)", "crop_area_ha": "Area of this crop on the plot (ha)",
    "harvested_area_ha": "Harvested area (ha)", "yield_kg_ha": "Yield (kg/ha), as computed by NISR",
    "weight": "Survey weight (plot expansion factor)",
    "w_area_ha": "Weighted harvested area = harvested_area_ha x weight",
    "fert_record_found": "1 = plot found in fertilizer file",
    "usable_yield": "1 = positive yield, harvested area and weight (and crop share not imputed)",
    "share_imputed": "1 = crop share imputed (NISR 2024 B screening lists one crop per plot); yield approximate",
    "extreme_yield": "1 = above 99th percentile (crop x season x year)",
}


# ------------------------------------------------------------------ helpers
def read_table(path):
    path = str(path)
    if path.lower().endswith(".dta"):
        return pd.read_stata(path, convert_categoricals=True)
    sep = "\t" if open(path, encoding="utf-8", errors="ignore").readline().count("\t") > 2 else ","
    return pd.read_csv(path, sep=sep, low_memory=False, encoding_errors="replace")


def text(s):
    s = pd.Series(s)
    return s.astype(object).where(s.notna(), "").astype(str).str.strip().str.lower()


def yes(series):
    s = text(series)
    return pd.Series(np.where(s.isin(YES), 1.0, np.where(s.isin(NO), 0.0, np.nan)), index=s.index)


def season_of(path):
    folder = None
    for part in reversed(Path(path).parts[:-1]):
        m = re.fullmatch(r"season\s*([abc])", part.strip(), re.I)
        if m:
            folder = m.group(1).upper()
            break
    name = Path(path).stem
    m = re.search(r"season[\s_-]*([abc])(?![a-z])", name, re.I) or re.search(r"pesticide([abc])\d{4}", name, re.I)
    return (m.group(1).upper() if m else None) or folder, folder


def find_files(root, seasons=("A", "B")):
    for ydir in sorted(p for p in Path(root).iterdir() if p.is_dir() and re.fullmatch(r"\d{4}", p.name)):
        files = [f for f in ydir.rglob("*") if f.is_file() and f.suffix.lower() in EXT_RANK]
        for season in seasons:
            def pick(regex):
                c = [f for f in files if re.search(regex, f.name, re.I) and season_of(f)[0] == season]
                return sorted(c, key=lambda f: (season_of(f)[1] not in (None, season),
                                                EXT_RANK[f.suffix.lower()], len(str(f))))[0] if c else None
            prod, fert, scr = pick(r"production"), pick(r"fertili"), pick(r"screening(?!_agro|_anti)")
            if prod:
                yield int(ydir.name), season, str(prod), str(fert) if fert else None, str(scr) if scr else None


def fert_features(path):
    """Plot-level flags and inorganic kg from the fertilizer file (wide 2023/2025 or long 2022 layout)."""
    f = read_table(path)
    cols = list(f.columns)
    slots = lambda q: {re.sub(rf"^s3q{q}_?", "", c) or "0": c for c in cols if re.fullmatch(rf"s3q{q}_?[1-4]?", c)}
    types, units, qty = slots(10), slots(11), slots(12)
    lime = np.zeros(len(f))
    kg = np.zeros(len(f))
    for k, tcol in types.items():
        t = text(f[tcol])
        is_lime = t.str.contains("|".join(LIME_WORDS)).values
        lime = np.maximum(lime, is_lime.astype(float))
        if k in units and k in qty:
            is_kg = text(f[units[k]]).str.startswith("kg").values
            q = pd.to_numeric(f[qty[k]], errors="coerce").fillna(0).values
            kg += np.where(is_kg & ~is_lime, q, 0)
    out = pd.DataFrame({"segment_id": f["Segment_ID"].values, "plot_no": f["s2q1"].values,
                        "lime": lime, "inorganic_kg": kg})
    for name, c in FERT_FLAGS.items():
        out[f"f_{name}"] = yes(f[c]).values if c in cols else np.nan
    agg = {c: "max" for c in out.columns if c not in ("segment_id", "plot_no", "inorganic_kg")}
    agg["inorganic_kg"] = "sum"                      # long layout: several rows (fertilizer types) per plot
    return out.groupby(["segment_id", "plot_no"], as_index=False).agg(agg)


PERENNIAL = ("banana", "cassava", "coffee", "tea", "fruit", "avocado", "mango", "papaya", "guava", "lemon",
             "orange", "mandarin", "mandaline", "passion", "pineapple", "sugar", "macadamia", "tree tomato")


# Reference crop shares for screening files that list only one crop per plot (NISR 2024 Season B).
# Filled by build_share_reference() from the complete screening files; these defaults are used otherwise
# (median share in 2025 A by number of crops on the plot).
SHARE_REF = {"crop_n": {}, "n": {1: 100.0, 2: 60.0, 3: 50.0, 4: 40.0}}
USE_IMPUTED_SHARES = False   # True = imputed shares also give a usable yield (default: kept out of models)


def _screening_shares(scr_path):
    s = read_table(scr_path)
    sh = (s[["Segment_ID", "s2q1", "s3q1", "s3q2_1"]]
          .rename(columns={"Segment_ID": "segment_id", "s2q1": "plot_no", "s3q1": "crop", "s3q2_1": "share_pct"}))
    sh["crop"] = sh.crop.astype(object).where(sh.crop.notna(), "").astype(str).str.strip()
    sh["share_pct"] = pd.to_numeric(sh.share_pct, errors="coerce")
    one_per_plot = not s.duplicated(["Segment_ID", "s2q1"]).any()
    return sh.dropna(subset=["share_pct"]).drop_duplicates(["segment_id", "plot_no", "crop"]), one_per_plot


def build_share_reference(files, log=None):
    """Median crop share by crop x number of crops on the plot, from screening files that list every crop."""
    parts = []
    for _, _, _, _, sp in files:
        if sp:
            try:
                sh, one = _screening_shares(sp)
            except Exception:
                continue
            if not one:
                sh["n"] = sh.groupby(["segment_id", "plot_no"]).crop.transform("size").clip(upper=4)
                parts.append(sh)
    if parts:
        r = pd.concat(parts, ignore_index=True)
        cn = r.groupby(["crop", "n"]).share_pct.agg(["median", "size"])
        SHARE_REF["crop_n"] = cn.loc[cn["size"] >= 30, "median"].to_dict()
        SHARE_REF["n"] = r.groupby("n").share_pct.median().to_dict()
        if log is not None:
            log.append(f"Crop-share reference: {len(parts)} complete screening files, {len(r):,} plot-crops")


def derive_area_yield(d, p, cfg, scr_path, year, season, log):
    """Yield = harvest kg / (plot area x crop share). Crop share comes from the screening file.
    Some NISR screening files (2024 Season B) keep only ONE crop per plot. For the other crops of a mixed
    plot the share is then imputed (median for that crop and number of crops on the plot) and flagged
    share_imputed = 1; by default those records get no usable yield."""
    d["share_imputed"] = 0
    if not scr_path:
        log.append(f"{year}{season}: screening file not found -> cannot derive crop area and yield")
        return d
    share, one_per_plot = _screening_shares(scr_path)
    d = d.merge(share, on=["segment_id", "plot_no", "crop"], how="left")
    found = d.share_pct.notna().mean()
    perennial = text(d.crop).str.contains("|".join(PERENNIAL)).values
    if one_per_plot:
        n = d.groupby(["segment_id", "plot_no"]).crop.transform("size").clip(upper=4)
        ref = pd.Series([SHARE_REF["crop_n"].get((c, k), SHARE_REF["n"].get(k, np.nan))
                         for c, k in zip(d.crop, n)], index=d.index)
        # single-crop plot not in screening: the whole plot unless screening says otherwise
        fill = d.share_pct.isna() & ~perennial
        d.loc[fill, "share_imputed"] = 1
        d["share_pct"] = d.share_pct.fillna(ref)
        log.append(f"{year}{season}: NOTE the NISR screening file lists only one crop per plot; exact crop share "
                   f"for {found:.0%} of records, imputed for {d.share_imputed.mean():.0%} (flag share_imputed=1, "
                   f"{'used' if USE_IMPUTED_SHARES else 'not used'} as usable yield)")
    harvest = pd.to_numeric(p[cfg["harvest_kg"]], errors="coerce").values
    d["crop_area_ha"] = d.plot_area_ha * d.share_pct / 100
    d["harvested_area_ha"] = np.where(perennial, np.nan, d.crop_area_ha)
    d["yield_kg_ha"] = np.where(perennial | (d.crop_area_ha <= 0), np.nan, harvest / d.crop_area_ha)
    log.append(f"{year}{season}: yield derived from harvest / (plot area x crop share); crop share found for "
               f"{found:.0%} of records; perennial crops (banana, cassava, fruit...) left blank")
    return d.drop(columns="share_pct")


def plot_flag(d, name, any_name):
    """Production value if present, else fertilizer-file value; 'any plot = No' implies this plot = No."""
    nan = pd.Series(np.nan, index=d.index)
    v = d[f"p_{name}"].combine_first(d[f"f_{name}"] if f"f_{name}" in d else nan)
    if any_name:
        a = d[f"p_{any_name}"].combine_first(d[f"f_{any_name}"] if f"f_{any_name}" in d else nan)
        v[v.isna() & (a == 0)] = 0.0
    return v


# ------------------------------------------------------------------ one year x season
def prepare_one(year, season, prod_path, fert_path, log, scr_path=None):
    if year not in PROD:
        log.append(f"{year}{season}: no column settings for this year -> skipped (add PROD[{year}])")
        return None
    cfg = {**COMMON, **PROD[year]}
    p = read_table(prod_path).reset_index(drop=True)
    get = lambda k: p[cfg[k]] if cfg.get(k) and cfg[k] in p.columns else pd.Series(np.nan, index=p.index)
    missing = [v for k, v in cfg.items() if isinstance(v, str) and v not in p.columns]
    if missing:
        log.append(f"{year}{season}: expected production columns not found: {missing}")

    d = pd.DataFrame({"year": year, "season": season}, index=p.index)
    for k in ["segment_id", "province", "stratum", "farmer_type", "farmer_sex", "plot_no", "crop_category"]:
        d[k] = get(k).astype(object).values
    for k in ["province", "stratum", "farmer_type", "farmer_sex", "crop_category"]:
        d[k] = get(k).astype(object).where(get(k).notna(), "").astype(str).str.strip().values
    d["district"] = text(get("district")).str.title().replace({"Nyarugenege": "Nyarugenge"}).values
    d["crop"] = get("crop").astype(object).astype(str).str.strip().values
    d["is_lsf"] = (text(get("stratum")).str.contains("lsf|large") |
                   text(get("farmer_type")).str.contains("large")).astype(int).values
    d["farmer_age"] = pd.to_numeric(get("farmer_age"), errors="coerce").values
    seed = text(get("seed_type"))
    d["improved_seed"] = np.where(seed.str.contains("improved|1&2"), 1.0,
                                  np.where(seed.str.contains("tradition"), 0.0, np.nan))

    plot_ha = pd.to_numeric(get("plot_area_ha"), errors="coerce")
    plot_ha = plot_ha.fillna(pd.to_numeric(get("plot_area_m2"), errors="coerce") / 1e4)
    crop_ha = pd.to_numeric(get("crop_area_ha"), errors="coerce")
    if cfg.get("crop_share_pct"):
        crop_ha = crop_ha.fillna(plot_ha * pd.to_numeric(get("crop_share_pct"), errors="coerce") / 100)
    d["plot_area_ha"], d["crop_area_ha"] = plot_ha.values, crop_ha.values
    d["harvested_area_ha"] = pd.to_numeric(get("harvested_area_ha"), errors="coerce").values
    d["yield_kg_ha"] = pd.to_numeric(get("yield_kg_ha"), errors="coerce").values
    d["share_imputed"] = 0
    if cfg.get("crop_share_from_screening"):
        d = derive_area_yield(d, p, cfg, scr_path, year, season, log)
    d["weight"] = pd.to_numeric(get("weight"), errors="coerce").values
    for k in ["erosion_degree", "anti_erosion_plot", "consolidated_site", "mechanized_plot", "irrigated_plot"]:
        d[f"raw_{k}"] = get(k).values
    for name in FERT_FLAGS:
        d[f"p_{name}"] = yes(get(name)).values

    if fert_path:
        ff = fert_features(fert_path)
        d = d.merge(ff, on=["segment_id", "plot_no"], how="left", indicator=True)
        d["fert_record_found"] = (d.pop("_merge") == "both").astype(int)
    else:
        d["fert_record_found"], d["lime"], d["inorganic_kg"] = 0, np.nan, np.nan
        log.append(f"{year}{season}: no fertilizer file found")
    d["organic_fert"] = plot_flag(d, "organic_plot", "organic_any")
    d["inorganic_fert"] = plot_flag(d, "inorganic_plot", "inorganic_any")
    d["micronutrient"] = plot_flag(d, "micronutrient_plot", None).fillna(0)
    d["pesticide"] = plot_flag(d, "pesticide_plot", "pesticide_any")
    d["inorganic_kg_ha"] = np.where(d.inorganic_fert == 1, d.inorganic_kg / d.plot_area_ha,
                                    np.where(d.inorganic_fert == 0, 0.0, np.nan))
    d.loc[d.fert_record_found == 0, ["lime", "inorganic_kg_ha"]] = np.nan
    d.loc[d.inorganic_kg_ha > 1000, "inorganic_kg_ha"] = np.nan          # implausible dose (unit/area error)

    ero = text(d["raw_erosion_degree"])
    d["erosion_degree"] = [next((v for k, v in EROSION.items() if x.startswith(k)), np.nan) for x in ero]
    d["anti_erosion"] = yes(d["raw_anti_erosion_plot"]).values
    d["consolidated_site"] = yes(d["raw_consolidated_site"]).values
    d["mechanized"] = yes(d["raw_mechanized_plot"]).values
    d["irrigated"] = yes(d["raw_irrigated_plot"]).values
    # Skip pattern: the plot question is skipped when the farmer answered "no" for all plots, so in years
    # where the question exists, a blank means "no".
    for out_col, key in [("anti_erosion", "anti_erosion_plot"), ("mechanized", "mechanized_plot"),
                         ("irrigated", "irrigated_plot")]:
        if isinstance(cfg.get(key), str) and cfg[key] in p.columns:
            d[out_col] = d[out_col].fillna(0.0)

    d["w_area_ha"] = d.harvested_area_ha * d.weight
    ok = (d.yield_kg_ha > 0) & (d.harvested_area_ha > 0) & d.weight.notna()
    if not USE_IMPUTED_SHARES:
        ok &= d.share_imputed == 0
    d["usable_yield"] = ok.astype(int)
    q99 = d[ok].groupby("crop").yield_kg_ha.transform(lambda s: s.quantile(.99))
    d["extreme_yield"] = 0
    d.loc[q99.index, "extreme_yield"] = (d.loc[q99.index, "yield_kg_ha"] > q99).astype(int)
    log.append(f"{year}{season}: {len(d):,} crop records | usable yield {int(ok.sum()):,} | fertilizer-file match "
               f"{d.fert_record_found.mean():.0%} | LSF {d.is_lsf.mean():.1%} | inorganic known "
               f"{d.inorganic_fert.notna().mean():.0%} | manure known {d.organic_fert.notna().mean():.0%}")
    return d


# ------------------------------------------------------------------ outputs
SHARES = ["improved_seed", "organic_fert", "inorganic_fert", "lime", "pesticide", "anti_erosion", "irrigated"]
KEEP = ["year", "season", "segment_id", "province", "district", "stratum", "is_lsf", "farmer_type", "farmer_sex",
        "farmer_age", "plot_no", "crop", "crop_category", "improved_seed", "organic_fert", "inorganic_fert",
        "inorganic_kg_ha", "lime", "micronutrient", "pesticide", "erosion_degree", "anti_erosion",
        "consolidated_site", "mechanized", "irrigated", "plot_area_ha", "crop_area_ha", "harvested_area_ha",
        "yield_kg_ha", "share_imputed", "weight", "w_area_ha", "fert_record_found", "usable_yield", "extreme_yield"]


def district_summary(d):
    s = d[(d.is_lsf == 0) & (d.usable_yield == 1) & (d.extreme_yield == 0)]
    def agg(x):
        w = x.w_area_ha
        r = {"plots": len(x), "segments": x.segment_id.nunique(), "weighted_area_ha": w.sum(),
             "yield_kg_ha": (x.yield_kg_ha * w).sum() / w.sum()}
        for c in SHARES:
            m = x[c].notna()
            r[f"{c}_share_area"] = (x.loc[m, c] * w[m]).sum() / w[m].sum() if m.any() else np.nan
        m = x.inorganic_kg_ha.notna()
        r["inorganic_kg_ha_mean"] = (x.loc[m, "inorganic_kg_ha"] * w[m]).sum() / w[m].sum() if m.any() else np.nan
        return pd.Series(r)
    return s.groupby(["year", "season", "district", "crop"]).apply(agg).reset_index()


def validate(summary, panel_path, log):
    pub = pd.read_csv(panel_path)
    rows = []
    for (y, s, c), g in summary.groupby(["year", "season", "crop"]):
        p = pub[(pub.year == y) & (pub.season == s) & (pub.crop == c)].set_index("district").yield_kg_ha
        j = pd.concat([g.set_index("district").yield_kg_ha.rename("micro"), p.rename("pub")], axis=1).dropna()
        if len(j) >= 10:
            rows.append(f"  {y}{s} {c:14s} districts {len(j):2d} | median ratio {np.median(j.micro / j.pub):.2f} "
                        f"| correlation {j.corr().iloc[0, 1]:.2f}")
    log.append("\nValidation against NISR published district yields (smallholders; microdata / published):")
    log.extend(rows or ["  no overlapping crops/years found"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", default="data/model_data")
    ap.add_argument("--inspect", action="store_true")
    ap.add_argument("--seasons", default="A,B", help="Seasons to include, e.g. A,B")
    ap.add_argument("--use-imputed-shares", action="store_true",
                    help="also treat yields from imputed crop shares (2024 B mixed plots) as usable")
    ap.add_argument("--validate", help="sas_district_yield_panel.csv, to check against published yields")
    a = ap.parse_args()
    files = list(find_files(a.inp, tuple(x.strip().upper() for x in a.seasons.split(","))))
    if not files:
        sys.exit(f"No production files (csv/dta) found under {a.inp}")
    if a.inspect:
        for y, s, pp, fp, sp in files:
            print(f"\n===== {y} Season {s}\n  production: {pp}\n  fertilizer: {fp}\n  screening:  {sp}")
            for path in [pp, fp]:
                if path:
                    cols = list(read_table(path).columns)
                    print(f"\n{y} {s} {Path(path).name} ({len(cols)} columns):\n  " + ", ".join(cols))
        return
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    log = []
    global USE_IMPUTED_SHARES
    USE_IMPUTED_SHARES = a.use_imputed_shares
    build_share_reference(files, log)
    parts = [x for x in (prepare_one(y, s, pp, fp, log, sp) for y, s, pp, fp, sp in files) if x is not None]
    d = pd.concat(parts, ignore_index=True)[KEEP]
    d.to_csv(out / "plot_crop_dataset.csv", index=False)
    summ = district_summary(d)
    summ.to_csv(out / "district_crop_summary.csv", index=False)
    if a.validate:
        validate(summ, a.validate, log)
    pd.DataFrame([{"column": k, "meaning": v} for k, v in DICTIONARY.items()]).to_csv(out / "data_dictionary.csv", index=False)
    (out / "data_quality_report.txt").write_text("\n".join(log) + "\n")
    print("\n".join(log))
    print(f"\nSaved {len(d):,} rows to {out / 'plot_crop_dataset.csv'} (+ district summary, dictionary, report).")


if __name__ == "__main__":
    main()

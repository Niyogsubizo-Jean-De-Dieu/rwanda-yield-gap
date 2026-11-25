"""
Read NISR Seasonal Agricultural Survey microdata 2017-2021 into the same plot x crop layout that
prepare_microdata.py builds for 2022-2025.

The older years differ from 2022-2025 in file layout and question numbers:
  2017, 2018  small-scale (SSF) and large-scale (LSF) farms in separate files; segment = s1q0;
              crop = s2q6; plot weight (WH_Plot) only in the screening file; LSF identified by LSF_ID
  2019        one file per season; crop = s2q6; harvested area in ha; plot weight in the screening file
  2020, 2021  close to 2022: crop = s2q4; plot weight in the production file; no harvested-area column,
              so harvested area = crop area x (plants harvested / plants) for perennials, crop area otherwise.
              In 2021 the production file's crop area is the whole plot on mixed plots, so the crop's own
              area is taken from the screening file.
Yield = total harvest (kg) / harvested area (ha). NISR's own yield column does not exist in these years.
Lime is not a fertilizer option before 2022, so it is left blank (NaN) for these years.

Folder layout: data/microdata/<year>/ unzipped as downloaded (STATA .dta files).
"""
import glob
import os
import re

import numpy as np
import pandas as pd

YEARS = (2017, 2018, 2019, 2020, 2021)

# column settings; None = not available in that year
CFG = {
    2017: dict(split_lsf=True, segment="s1q0", lsf_id="LSF_ID", crop="s2q6", harvest="s2q22",
               plot_m2="s2q2", crop_m2="s2q7", harv_m2=None, harv_ha=None, crop_ha=None,
               trees_total="s2q18_1", trees_harv="s2q18_2", seed="s2q12",
               farmer_type=None, sex=None, age=None,
               scr_plot="s2q2", scr_crop="s2q11", scr_weight="WH_Plot",
               f_org="s3q1", f_inorg="s3q5", f_type="s3q6", f_unit="s3q7", f_qty="s3q8",
               f_inorg_lsf="s3q5", f_type_lsf="s3q6", f_unit_lsf="s3q7", f_qty_lsf="s3q8",
               f_pest=None, irrig="s4q17", erosion=None, anti_erosion=None),
    2018: dict(split_lsf=True, segment="s1q0", lsf_id="LSF_ID", crop="s2q6", harvest="s2q21",
               plot_m2="s2q2", crop_m2="s2q7", harv_m2="Harvested_area", harv_ha=None, crop_ha=None,
               # the 2018 LSF files give Harvested_area at 1/10 of the crop area (LSF maize "yield" 24 t/ha):
               # for large farms use the crop area instead
               lsf_use_crop_area=True,
               trees_total=None, trees_harv=None, seed="s2q10",
               farmer_type=None, sex=None, age=None,
               scr_plot="s2q2", scr_crop="s2q11", scr_weight="WH_Plot",
               f_org="s3q1", f_inorg="s3q5", f_type="s3q6", f_unit="s3q7", f_qty="s3q8",
               f_inorg_lsf="s3q6", f_type_lsf="s3q7", f_unit_lsf="s3q8", f_qty_lsf="s3q9",
               f_pest=None, irrig="s4q17", erosion=None, anti_erosion=None),
    2019: dict(split_lsf=False, segment="Segment_ID", crop="s2q6", harvest="s2q21",
               plot_m2="s2q2",   # m2 in Season A, ha in Season B: unit detected in _production
               crop_m2=None, harv_m2=None, harv_ha="Harvested_Area", crop_ha="s2q7",
               trees_total=None, trees_harv=None, seed="s2q10",
               farmer_type="s2q3_1", sex=None, age=None,
               scr_plot="s2q2", scr_crop="s2q11", scr_weight="Weight",
               f_org="s3q1", f_inorg="s3q5", f_type="s3q6", f_unit="s3q7", f_qty="s3q8",
               f_pest="s3q13", irrig="s4q13", erosion="s4q1", anti_erosion="s4q2"),
    2020: dict(split_lsf=False, segment="Segment_ID", crop="s2q4", harvest="s2q21",
               plot_m2="s2q2", crop_m2=None, harv_m2=None, harv_ha=None, crop_ha="Crop_Area",
               trees_total="s2q5", trees_harv="s2q6", seed="s2q11",
               farmer_type="s1q7", sex="s1q8", age="s1q9", weight="Plot_weight",
               f_org="s3q3", f_org_any="s3q1", f_inorg="s3q9", f_inorg_any="s3q7",
               f_type="s3q10", f_unit="s3q11", f_qty="s3q12", f_pest="s3q19",
               irrig="s4q13", erosion="s4q1", anti_erosion="s4q3"),
    2021: dict(split_lsf=False, segment="Segment_ID", crop="s2q4", harvest="s2q21",
               plot_m2="s2q2", crop_m2=None, harv_m2=None, harv_ha=None, crop_ha="Crop_Area",
               trees_total="s2q5", trees_harv="s2q6", seed="s2q11",
               farmer_type="s1q7", sex="s1q8", age="s1q9", weight="finalplot_weight",
               # 2021 production Crop_Area is the whole plot even on mixed plots: take the crop's own area
               # from the screening file (one row per crop on the plot)
               crop_area_from_screening=True, scr_plot="s2q1", scr_crop="s3q1", scr_area="Crop_Area",
               f_org="s3q3", f_org_any="s3q1", f_inorg="s3q9", f_inorg_any="s3q7",
               f_type="s3q10", f_unit="s3q11", f_qty="s3q12", f_pest="s3q19",
               irrig="s4q13", erosion="s4q1", anti_erosion="s4q3"),
}
EROSION = {"very low": 0, "weak": 1, "low": 1, "moderate": 2, "high": 3, "severe": 3, "very high": 3}


# ------------------------------------------------------------------ reading
def read_labeled(path):
    """Read a Stata file and apply value labels column by column (some NISR files repeat a label,
    which makes pandas' automatic conversion fail)."""
    with pd.io.stata.StataReader(path) as r:
        d = r.read(convert_categoricals=False)
        vl = r.value_labels()
        lbl = dict(zip(r._varlist, r._lbllist))
    for c in d.columns:
        m = vl.get(lbl.get(c) or "")
        if m:
            d[c] = d[c].map(lambda v, m=m: m.get(v, v) if pd.notna(v) else v)
    return d


def _files(ydir, season, kind, farm=None):
    pats = {"production": r"crop production", "fertilizer": r"fertili",
            "screening": r"screening(?!_agro|_anti)", "practice": r"agricultural practice|irrigation_soil"}
    out = []
    for f in glob.glob(os.path.join(ydir, "**", "*.dta"), recursive=True):
        n = os.path.basename(f)
        if re.search(pats[kind], n, re.I) and re.search(rf"season[ _-]?{season}(?![a-z])", n, re.I):
            if farm is None or re.search(rf"_{farm}_", n):
                out.append(f)
    return sorted(out, key=len)


def has_season(ydir, season):
    return bool(_files(ydir, season, "production"))


def text(s):
    s = pd.Series(s)
    return s.astype(object).where(s.notna(), "").astype(str).str.strip().str.lower()


def yes(s):
    t = text(s)
    return pd.Series(np.where(t.str.startswith("yes") | t.isin(["1", "1.0"]), 1.0,
                              np.where(t.str.startswith("no") | t.isin(["2", "2.0"]), 0.0, np.nan)), index=t.index)


def num(d, c):
    return pd.to_numeric(d[c], errors="coerce") if c and c in d.columns else pd.Series(np.nan, index=d.index)


def key(seg, plot):
    """Join key: segment (or LSF id) + plot number, as clean strings."""
    s = pd.Series(seg).astype(object).map(lambda v: str(int(v)) if isinstance(v, (int, float, np.integer, np.floating))
                                           and pd.notna(v) else str(v).strip())
    p = pd.to_numeric(pd.Series(plot), errors="coerce").map(lambda v: str(int(v)) if pd.notna(v) else "")
    return (s.values + "_" + p.values)


# ------------------------------------------------------------------ pieces
def _screening_crop_area(ydir, season, c):
    """Crop area (ha) per segment x plot x crop from the screening file (2021)."""
    f = _files(ydir, season, "screening")
    if not f:
        return None
    s = read_labeled(f[0])
    a = pd.DataFrame({"k": key(s[c["segment"]], s[c["scr_plot"]]),
                      "crop": s[c["scr_crop"]].astype(object).astype(str).str.strip(),
                      "a": pd.to_numeric(s[c["scr_area"]], errors="coerce")})
    return a.dropna().groupby(["k", "crop"]).a.first()


def _production(path, c, lsf, scr_area=None):
    p = read_labeled(path)
    seg = ("LSF" + p[c["lsf_id"]].astype(str)) if lsf else p[c["segment"]]
    d = pd.DataFrame(index=p.index)
    d["segment_id"] = pd.Series(seg).astype(object).map(lambda v: str(int(v)) if isinstance(v, float) and pd.notna(v) else str(v)).values
    d["plot_no"] = num(p, "s2q1").values
    d["k"] = key(d.segment_id, d.plot_no)
    d["province"] = text(p.get("s1q1", "")).str.title().values if "s1q1" in p else ""
    d["district"] = text(p["s1q2"]).str.title().replace({"Nyarugenege": "Nyarugenge"}).values
    d["stratum"] = ("LSF" if lsf else p["s1q3"].astype(object).where(p["s1q3"].notna(), "").astype(str).str.strip().values) \
        if (lsf or "s1q3" in p) else ""
    ft = p[c["farmer_type"]] if c.get("farmer_type") and c["farmer_type"] in p else pd.Series("", index=p.index)
    d["farmer_type"] = ("large scale farm (LSF file)" if lsf else ft.astype(object).where(ft.notna(), "").astype(str).str.strip().values)
    d["is_lsf"] = (lsf or False) * 1
    if not lsf:
        d["is_lsf"] = (text(d.stratum).str.contains("lsf|large") | text(d.farmer_type).str.contains("large")).astype(int).values
    d["farmer_sex"] = p[c["sex"]].astype(object).where(p[c["sex"]].notna(), "").astype(str).str.strip().values \
        if c.get("sex") and c["sex"] in p else ""
    d["farmer_age"] = num(p, c.get("age")).values
    d["crop"] = p[c["crop"]].astype(object).astype(str).str.strip().values
    d["crop_category"] = ""
    seed = text(p[c["seed"]]) if c.get("seed") in p else pd.Series("", index=p.index)
    d["improved_seed"] = np.where(seed.str.contains("improved|1&2"), 1.0, np.where(seed.str.contains("trad"), 0.0, np.nan))  # 2017 B label: "Tradional seeds"

    raw_plot = num(p, c.get("plot_m2"))
    plot_ha = raw_plot if raw_plot.median() < 20 else raw_plot / 1e4   # some files already give hectares
    crop_ha = num(p, c.get("crop_ha")).fillna(num(p, c.get("crop_m2")) / 1e4)
    if scr_area is not None:
        k = key(p[c["segment"]], p["s2q1"])
        crop = p[c["crop"]].astype(object).astype(str).str.strip().values
        crop_ha = pd.Series([scr_area.get((a, b), np.nan) for a, b in zip(k, crop)], index=p.index)
    harv_ha = num(p, c.get("harv_ha")).fillna(num(p, c.get("harv_m2")) / 1e4)
    if lsf and c.get("lsf_use_crop_area"):
        harv_ha = pd.Series(np.nan, index=p.index)
    if harv_ha.isna().all():
        # no harvested-area column: crop area, scaled by the share of plants harvested for perennials
        tot, hv = num(p, c.get("trees_total")), num(p, c.get("trees_harv"))
        ratio = (hv / tot).where((tot > 0) & hv.notna()).clip(0, 1)
        harv_ha = crop_ha * ratio.fillna(1.0)
    d["plot_area_ha"] = plot_ha.values
    d["crop_area_ha"] = crop_ha.values
    d["harvested_area_ha"] = harv_ha.values
    harvest = num(p, c["harvest"])
    d["yield_kg_ha"] = np.where(harv_ha > 0, harvest / harv_ha, np.nan)
    d["weight"] = (1.0 if lsf else num(p, c.get("weight")).values)
    return d


def _weights(ydir, season, c, log, tag):
    """Plot weight from the screening file (2017-2019), one per segment x plot."""
    f = _files(ydir, season, "screening", "SSF" if c["split_lsf"] else None)
    if not f:
        log.append(f"{tag}: screening file not found -> no weights")
        return pd.Series(dtype=float)
    s = read_labeled(f[0])
    col = {k.lower(): k for k in s.columns}          # 'Weight' in 2019 A, 'weight' in 2019 B
    wcol = col.get(c["scr_weight"].lower())
    if wcol is None:
        log.append(f"{tag}: weight column {c['scr_weight']} not in screening file -> no weights")
        return pd.Series(dtype=float)
    w = pd.DataFrame({"k": key(s[c["segment"]], s[c["scr_plot"]]), "w": pd.to_numeric(s[wcol], errors="coerce")})
    return w.dropna().groupby("k").w.first()


def _fertilizer(paths, c, lsf):
    parts = []
    for path in paths:
        f = read_labeled(path)
        seg = ("LSF" + f[c["lsf_id"]].astype(str)) if lsf else f[c["segment"]]
        g = lambda name: c.get(f"{name}_lsf", c.get(name)) if lsf else c.get(name)
        out = pd.DataFrame({"k": key(seg, f["s2q1"])})
        out["organic_fert"] = yes(f[c["f_org"]]).values if c["f_org"] in f else np.nan
        out["inorganic_fert"] = yes(f[g("f_inorg")]).values if g("f_inorg") in f else np.nan
        for anyc, col in [("f_org_any", "organic_fert"), ("f_inorg_any", "inorganic_fert")]:
            if c.get(anyc) in f:            # 'no plot at all' => this plot = no
                a = yes(f[c[anyc]]).values
                out.loc[(out[col].isna()) & (a == 0), col] = 0.0
        unit = text(f[g("f_unit")]) if g("f_unit") in f else pd.Series("", index=f.index)
        q = num(f, g("f_qty"))
        factor = np.where(unit.str.startswith("kg"), 1.0, np.where(unit.str.match(r"^g\b|^g;|^g$"), 0.001, np.nan))
        out["kg"] = (q * factor).values
        out["kg_unknown_unit"] = (q.notna() & (q > 0) & np.isnan(factor)).values
        out["pesticide"] = yes(f[c["f_pest"]]).values if c.get("f_pest") in f else np.nan
        parts.append(out)
    if not parts:
        return None
    f = pd.concat(parts, ignore_index=True)
    return f.groupby("k").agg(organic_fert=("organic_fert", "max"), inorganic_fert=("inorganic_fert", "max"),
                              kg=("kg", lambda s: s.sum(min_count=1)), kg_unknown_unit=("kg_unknown_unit", "max"),
                              pesticide=("pesticide", "max"))


def _practices(paths, c, lsf):
    parts = []
    for path in paths:
        f = read_labeled(path)
        seg = ("LSF" + f[c["lsf_id"]].astype(str)) if lsf else f[c["segment"]]
        out = pd.DataFrame({"k": key(seg, f["s2q1"])})
        out["irrigated"] = yes(f[c["irrig"]]).values if c.get("irrig") in f else np.nan
        out["anti_erosion"] = yes(f[c["anti_erosion"]]).values if c.get("anti_erosion") in f else np.nan
        if c.get("erosion") in f:
            e = text(f[c["erosion"]])
            out["erosion_degree"] = [next((v for k, v in sorted(EROSION.items(), key=lambda kv: -len(kv[0]))
                                           if x.startswith(k)), np.nan) for x in e]
        else:
            out["erosion_degree"] = np.nan
        parts.append(out)
    if not parts:
        return None
    return pd.concat(parts, ignore_index=True).groupby("k").max()


# ------------------------------------------------------------------ one year x season
def prepare(year, season, ydir, log):
    c = CFG[year]
    tag = f"{year}{season}"
    pieces = []
    for lsf in ([False, True] if c["split_lsf"] else [False]):
        farm = ("LSF" if lsf else "SSF") if c["split_lsf"] else None
        prod = _files(ydir, season, "production", farm)
        if not prod:
            continue
        scr_area = _screening_crop_area(ydir, season, c) if c.get("crop_area_from_screening") else None
        d = _production(prod[0], c, lsf, scr_area)
        if not lsf and c["split_lsf"]:
            w = _weights(ydir, season, c, log, tag)
            d["weight"] = d.k.map(w).values
        elif not lsf and year == 2019:
            w = _weights(ydir, season, c, log, tag)
            d["weight"] = d.k.map(w).values
            d.loc[d.is_lsf == 1, "weight"] = d.loc[d.is_lsf == 1, "weight"].fillna(1.0)
        fert = _fertilizer(_files(ydir, season, "fertilizer", farm), c, lsf)
        if fert is not None:
            d = d.merge(fert, left_on="k", right_index=True, how="left", indicator=True)
            d["fert_record_found"] = (d.pop("_merge") == "both").astype(int)
        else:
            d["fert_record_found"] = 0
            d[["organic_fert", "inorganic_fert", "kg", "kg_unknown_unit", "pesticide"]] = np.nan
        prac = _practices(_files(ydir, season, "practice", farm), c, lsf)
        if prac is not None:
            d = d.merge(prac, left_on="k", right_index=True, how="left")
        else:
            d[["irrigated", "anti_erosion", "erosion_degree"]] = np.nan
        pieces.append(d)
    d = pd.concat(pieces, ignore_index=True)
    d.insert(0, "season", season)
    d.insert(0, "year", year)
    d["inorganic_kg_ha"] = np.where(d.inorganic_fert == 1, d.kg / d.plot_area_ha,
                                    np.where(d.inorganic_fert == 0, 0.0, np.nan))
    d.loc[(d.inorganic_fert == 1) & (d.kg_unknown_unit == True), "inorganic_kg_ha"] = np.nan  # noqa: E712
    d.loc[d.fert_record_found == 0, "inorganic_kg_ha"] = np.nan
    d.loc[d.inorganic_kg_ha > 1000, "inorganic_kg_ha"] = np.nan
    d["lime"] = np.nan                      # not asked as a fertilizer type before 2022
    d["micronutrient"] = np.nan
    d["consolidated_site"] = np.nan
    d["mechanized"] = np.nan
    d["share_imputed"] = 0
    log.append(f"{tag}: legacy reader | weight found {d.weight.notna().mean():.0%} | fertilizer match "
               f"{d.fert_record_found.mean():.0%} | harvested area known {(d.harvested_area_ha > 0).mean():.0%}")
    return d.drop(columns=["k", "kg", "kg_unknown_unit"])

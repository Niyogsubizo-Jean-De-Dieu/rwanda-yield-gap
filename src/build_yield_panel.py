"""
Build a clean district x season x crop yield panel from NISR Seasonal Agricultural
Survey (SAS) table workbooks, 2017-2026.

Output: sas_district_yield_panel.csv with columns
  year, season, district, province, crop, yield_kg_ha, source_file, source_sheet

Notes
- 2015 and 2016 SAS tables only report yields by stratum, not district, so the
  district series starts in 2017.
- 2017 and 2018 tables have crops as rows and districts as columns; 2019+ have
  districts as rows. Orientation is detected automatically.
- 0, '-', and blanks mean "crop not grown / not estimated", so they become NaN.
- Season C covers mainly marshland/valley sites, not all districts.
- Old .xls files must first be converted to .xlsx (e.g. LibreOffice:
  soffice --headless --convert-to xlsx file.xls).
"""
import re
import sys
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/sas_published_tables")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/sas_district_yield_panel.csv")

DISTRICTS = {
    "Kigali City": ["Nyarugenge", "Gasabo", "Kicukiro"],
    "Southern": ["Nyanza", "Gisagara", "Nyaruguru", "Huye", "Nyamagabe", "Ruhango", "Muhanga", "Kamonyi"],
    "Western": ["Karongi", "Rutsiro", "Rubavu", "Nyabihu", "Ngororero", "Rusizi", "Nyamasheke"],
    "Northern": ["Rulindo", "Gakenke", "Musanze", "Burera", "Gicumbi"],
    "Eastern": ["Rwamagana", "Nyagatare", "Gatsibo", "Kayonza", "Kirehe", "Ngoma", "Bugesera"],
}
PROVINCE = {d: p for p, ds in DISTRICTS.items() for d in ds}
DNORM = {d.lower(): d for d in PROVINCE}

# Source tables: (file, sheet, year, season)
SOURCES = [
    ("USAS_2017_Tables.xlsx", ("Appendix", "Season A- Yield of main crops by district"), 2017, "A"),
    ("USAS_2017_Tables.xlsx", ("Appendix", "Season B-Yield of main crops by district"), 2017, "B"),
    ("USAS_2017_Tables.xlsx", ("Appendix", "Season C-Yield of main crops by district"), 2017, "C"),
    ("2018_Annual_Tables_Final_1.xlsx", "Appendix 9", 2018, "A"),
    ("2018_Annual_Tables_Final_1.xlsx", "Appendix 10", 2018, "B"),
    ("2018_Annual_Tables_Final_1.xlsx", "Appendix 11", 2018, "C"),
    ("SAS_2019__Annual_report__Tables.xlsx", "Table 13", 2019, "A"),
    ("SAS_2019__Annual_report__Tables.xlsx", "Table 14", 2019, "B"),
    ("SAS_2019__Annual_report__Tables.xlsx", "Table 15", 2019, "C"),
    ("USAS_2020__Final_Tables.xlsx", "Table 14", 2020, "A"),
    ("USAS_2020__Final_Tables.xlsx", "Table 15", 2020, "B"),
    ("USAS_2020__Final_Tables.xlsx", "Table 16", 2020, "C"),
    ("SAS_2021_Tables.xlsx", "Table 17", 2021, "A"),
    ("SAS_2021_Tables.xlsx", "Table 18", 2021, "B"),
    ("SAS_2021_Tables.xlsx", "Table 20", 2021, "C"),
    ("SAS_2022_Tables_0.xlsx", "Table 17", 2022, "A"),
    ("SAS_2022_Tables_0.xlsx", "Table 18", 2022, "B"),
    ("SAS_2022_Tables_0.xlsx", "Table 19", 2022, "C"),
    ("SAS_2023_Annual_Tables_3.xlsx", "Table 16", 2023, "A"),
    ("SAS_2023_Annual_Tables_3.xlsx", "Table 17", 2023, "B"),
    ("SAS_2023_Annual_Tables_3.xlsx", "Table 18", 2023, "C"),
    ("Tables_2024_Season_A_1.xlsx", "Table 11", 2024, "A"),
    ("Tables_2024_Season_B.xlsx", "Table 10", 2024, "B"),
    ("SAS_2025_Annual_Tables.xlsx", "Table 19", 2025, "A"),
    ("SAS_2025_Annual_Tables.xlsx", "Table 20", 2025, "B"),
    ("SAS_2025_Annual_Tables.xlsx", "Table 21", 2025, "C"),
    ("Tables_2026_Season_B.xlsx", "Table 11", 2026, "B"),
]

# Harmonise crop names across years; None = drop (aggregate groups / non-crop columns)
CROP_MAP = {
    "maize": "Maize", "sorghum": "Sorghum", "paddy rice": "Paddy rice", "wheat": "Wheat",
    "other cereals": "Other cereals", "chia seeds": "Chia seeds",
    "cassava": "Cassava", "sweet potato": "Sweet potato", "sweet potatoes": "Sweet potato",
    "irish potato": "Irish potato", "irish potatoes": "Irish potato",
    "yams & taro": "Yams & taro", "yarms & taro": "Yams & taro",
    "banana": "Banana (all)", "bananas": "Banana (all)",
    "cooking banana": "Cooking banana", "dessert banana": "Dessert banana",
    "banana for beer": "Beer banana",
    "beans": "Beans (all)", "bush beans": "Bush bean", "climbing beans": "Climbing bean",
    "small red bean": "Small red bean", "soya bean": "Soybean", "bean": "Beans (all)", "bush bean": "Bush bean", "climbing bean": "Climbing bean",
    "peas": "Peas", "pea": "Peas", "ground nuts": "Groundnuts", "groundnuts": "Groundnuts",
    "groundnut": "Groundnuts", "soya beans": "Soybean", "soybean": "Soybean",
    "vegetables": "Vegetables", "fruits": "Fruits", "fodder crops": "Fodder crops", "other crops": "Other crops",
}
DROP = {"cereals", "tubers and roots", "legumes and pulses", "vegetables and fruits"}


def norm_text(x):
    return re.sub(r"\s+", " ", str(x)).strip().lower() if x is not None else ""


def to_num(x):
    if x is None:
        return np.nan
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(",", "")
    try:
        return float(s)
    except ValueError:
        return np.nan  # '-', '', text


def get_grid(wb, sheet_spec):
    """Return list-of-lists for a sheet, or a sub-block when spec is (sheet, title)."""
    if isinstance(sheet_spec, tuple):
        sheet, title = sheet_spec
        rows = [list(r) for r in wb[sheet].iter_rows(values_only=True)]
        start = next(i for i, r in enumerate(rows) if r and norm_text(r[0]).startswith(title.lower()))
        block = []
        for r in rows[start + 1:]:
            if r and isinstance(r[0], str) and "yield of main crops by district" in r[0].lower():
                break  # next block
            if block and all(c is None for c in r[:5]) and len(block) > 3:
                break
            block.append(r)
        return block
    name = next(n for n in wb.sheetnames if n.strip() == sheet_spec.strip())
    return [list(r) for r in wb[name].iter_rows(values_only=True)]


def parse(grid):
    """Detect orientation by where district names sit, then return long records."""
    cells = [(i, j, DNORM[norm_text(v)]) for i, r in enumerate(grid) for j, v in enumerate(r)
             if norm_text(v) in DNORM]
    rows = {i for i, _, _ in cells}
    cols = {j for _, j, _ in cells}
    recs = []
    if len(cols) == 1:  # districts down a column, crops across a header row
        dcol = cols.pop()
        first = min(rows)
        hdr_i = max(i for i in range(first) if sum(isinstance(v, str) and norm_text(v) in CROP_MAP or norm_text(v) in DROP
                                                     for v in grid[i]) >= 2)
        hdr = grid[hdr_i]
        for i, j_, d in cells:
            for j, h in enumerate(hdr):
                if j == dcol or h is None:
                    continue
                recs.append((d, norm_text(h), to_num(grid[i][j] if j < len(grid[i]) else None)))
    elif len(rows) == 1:  # districts across a header row, crops down first column
        hrow = rows.pop()
        dcols = {j: d for _, j, d in cells}
        for r in grid[hrow + 1:]:
            if not r or not isinstance(r[0], str):
                continue
            crop = norm_text(r[0])
            for j, d in dcols.items():
                recs.append((d, crop, to_num(r[j] if j < len(r) else None)))
    else:
        raise ValueError("Could not detect table orientation")
    return recs


def main():
    out, unknown = [], set()
    books = {}
    for fname, spec, year, season in SOURCES:
        wb = books.setdefault(fname, openpyxl.load_workbook(RAW / fname, read_only=True, data_only=True))
        recs = parse(get_grid(wb, spec))
        sheet = spec if isinstance(spec, str) else spec[0]
        for d, crop, val in recs:
            if crop in DROP:
                continue
            if crop not in CROP_MAP:
                unknown.add(crop)
                continue
            out.append(dict(year=year, season=season, district=d, province=PROVINCE[d],
                            crop=CROP_MAP[crop], yield_kg_ha=val,
                            source_file=fname, source_sheet=sheet.strip()))
    df = pd.DataFrame(out)
    df.loc[df.yield_kg_ha <= 0, "yield_kg_ha"] = np.nan  # 0 / '-' = not grown
    df = df.dropna(subset=["yield_kg_ha"])
    # If a crop appears twice for the same district-season (e.g. duplicated header), keep first
    df = df.drop_duplicates(subset=["year", "season", "district", "crop"], keep="first")
    # Quality flags
    # 2017 cassava and banana yields are ~0.2-0.4x every later year in every district:
    # a change in reporting basis, not a real decline. Exclude them from trend analysis.
    df["quality_flag"] = ""
    brk = (df.year == 2017) & df.crop.isin(["Cassava", "Cooking banana", "Dessert banana", "Beer banana"])
    df.loc[brk, "quality_flag"] = "2017_method_break"
    # Values >3x or <1/3 of the district's own median for that crop and season
    key = ["district", "crop", "season"]
    ratio = df.yield_kg_ha / df.groupby(key).yield_kg_ha.transform("median")
    df.loc[(df.quality_flag == "") & ((ratio > 3) | (ratio < 1 / 3)), "quality_flag"] = "extreme_value"
    df.loc[df.season == "C", "quality_flag"] = df.loc[df.season == "C", "quality_flag"].replace(
        "", "season_C_sites_only")
    df = df.sort_values(["crop", "district", "year", "season"]).reset_index(drop=True)
    df.to_csv(OUT, index=False)
    unknown = {u for u in unknown if "seasonal agricultur" not in u}  # table footers
    if unknown:
        print("Ignored unrecognised columns/rows:", sorted(unknown))
    print(f"Wrote {len(df):,} rows to {OUT}")
    print(df.quality_flag.replace("", "ok").value_counts().to_string())
    return df


if __name__ == "__main__":
    main()

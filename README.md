# Rwanda Yield Gap Explorer

**NISR Big Data Hackathon 2026 · Track 1: Agricultural Productivity**

Where would fertilizer, improved seed and manure raise harvests most? This project combines NISR Seasonal Agricultural Survey (SAS) data with soil and satellite data. It shows, for every district and main crop, how yields have changed, what drives them, and how much extra production each farm input could bring.

| | |
| --- | --- |
| **Live dashboard** | `https://<github-user>.github.io/<repo-name>/` |
| **Demo video** | [`demo/demo.webm`](demo/demo.webm) (1 min 24 s) |
| **Run locally** | `python3 app.py` |

## 1. The problem and why it matters

Rwanda's second National Strategy for Transformation (NST2) and its agriculture plan, PSTA 5 (2024/25–2028/29), aim to raise crop productivity by about 50% by 2028/29. PSTA 5 sets yield targets per crop, for example maize 1.7 → 2.74 t/ha and beans 0.6 → 1.1 t/ha. It also aims to raise smallholder use of inorganic fertilizer (54.9% → 66.5%) and improved seed (35.9% → 50%) ([PSTA 5, MINAGRI](https://www.minagri.gov.rw/fileadmin/user_upload/Minagri/Publications/Policies_and_strategies/PSTA_5_Abridged_version_Final.pdf)).

Input budgets are limited, and input use is uneven. In 2025 Season A, inorganic fertilizer reached about two-thirds of maize area but only a third of bush bean area. The question for MINAGRI, RAB and district agronomists is: **in which district, for which crop and with which input does support raise production most?**

The dashboard answers this from data NISR already collects every season.

## 2. What data the dashboard uses

| Data | Source | What it gives |
| --- | --- | --- |
| SAS published district tables 2017–2026 | NISR | District yield trends (baseline to latest season) |
| SAS plot microdata 2022–2025, Seasons A and B | [NISR Microdata Portal](https://microdata.statistics.gov.rw/index.php/catalog) (catalog 103, 111, 113, 124) | 152,835 plot-crop records: yield, fertilizer, seed, manure, lime, erosion control, plot and farmer traits, survey weights |
| Soil and terrain | iSDAsoil, SRTM (Google Earth Engine) | Soil pH, carbon and nitrogen; elevation and slope of district cropland |
| Season weather and crop condition | MODIS NDVI/EVI and land temperature, CHIRPS rainfall, ERA5-Land, Sentinel-1 radar (Google Earth Engine) | 16-day anomalies per district and season, 2017–2026 |
| Policy targets | [PSTA 5](https://www.minagri.gov.rw/fileadmin/user_upload/Minagri/Publications/Policies_and_strategies/PSTA_5_Abridged_version_Final.pdf) | 2028/29 national yield targets shown on the charts |

The data used by the dashboard are in [`data/`](data/). They are all district-level aggregates; see [`data/README.md`](data/README.md). The raw microdata are too large and are governed by NISR's access terms, so they are not in this repository. Download them from the link above.

## 3. What the dashboard communicates and how to use it

Pick a **crop**, **season** and **district** at the top. Each page opens with a short **In brief** text that rewrites itself for your selection and states the main point, followed by at most three charts. Hover for exact values; click a district on the map to select it; switch **English / Kinyarwanda** in the side menu.

| Page | What it shows | Question it answers |
| --- | --- | --- |
| **Yield trends** (start) | Map of yield change since a baseline year; the district's yield against the national average and the PSTA 5 target; in brief: change, rank, distance to target, input use | Is this district improving, and how far is it from the target? |
| **What to do** | Map of the input each district should promote (fertilizer, improved seed, manure, lime or anti-erosion works); the district's yield today and with each input; top 10 districts by extra harvest. Choose one input to see where it pays off most | What should be done, where, first, and how much would it add? |
| **What drives yield** | The 10 factors that most separate high- from low-yield fields, for the chosen crop | What matters most, and how much is under farmers' control? |
| **How reliable** | Error of the model and of simple rules when each season is predicted from earlier seasons; validation table | How far can the results be trusted? |
| **About** | Purpose, data, method, limits, AI use | |

## 4. Method

1. **Survey data** (`src/prepare_microdata.py`): plot × crop records harmonized across four yearly layouts. Survey-weighted district yields match NISR's published tables (median ratio 0.89–1.04 for the main crops).
2. **Context features** (`src/build_model_dataset.py`): district soil, terrain and seasonal satellite anomalies joined to each plot.
3. **Yield model** (`src/train_model.py`): LightGBM on log yield with 42 features. Inputs are constrained to have non-negative effects.
4. **Validation:** unseen segments, unseen districts and an unseen year; a walk-forward test season by season (`src/compare_models.py`).
5. **Drivers:** mean absolute SHAP values per feature and group.
6. **Scenarios:**
    - Each 2025 plot that does not use an input is predicted again as if it did. Fertilizer is set at the typical dose of users of that crop.
    - Gains are summed with survey weights per district.
    - A lever is shown for a crop only if at least 200 surveyed plots use it and 200 do not.

### Main results

| Result | Value |
| --- | --- |
| District yield error in unseen districts | 17% (baseline 26%) |
| Largest driver group within a crop (SHAP) | Inputs and practices, 29%; top factor: fertilizer dose |
| Extra maize from fertilizer + improved seed + manure, 2025 A + B | about 107,000 t (+19%) |
| Priority districts for maize | Nyagatare, Kirehe, Ngoma, Kayonza, Gatsibo |
| Fertilizer response of maize | about +30% at 75 kg/ha, flattening above 150 kg/ha |

## 5. Repository structure

```
rwanda-yield-gap/
├── README.md
├── app.py                       # opens the dashboard locally (standard library only)
├── requirements.txt
├── data/                        # data used by the dashboard (district level) + link to the raw data
│   ├── README.md
│   ├── sas_district_yield_panel.csv
│   ├── gee_exports/             # soil, terrain and satellite features per district
│   ├── model_data/              # survey-weighted adoption and yields per district (plot-level files not published)
│   └── model_outputs/           # scenarios, SHAP, validation, walk-forward scores
├── src/                         # full pipeline, runs on any machine with Python 3.10+
├── notebooks/                   # 05 yield-gap model, 06 walk-forward validation (same code, with charts)
├── gee/                         # Google Earth Engine scripts used to extract the satellite features
├── docs/                        # the dashboard (published with GitHub Pages)
└── demo/                        # demo.webm and the script that records it
```

## 6. Run it

```bash
python3 -m pip install -r requirements.txt

# Dashboard only (uses the results already in data/)
python3 app.py

# Full pipeline (needs the NISR microdata in data/microdata/<year>/)
python3 src/build_model_dataset.py      # -> data/model_data/
python3 src/train_model.py              # model, validation, SHAP, scenarios -> data/model_outputs/
python3 src/compare_models.py           # walk-forward model comparison (optional, ~15 min)
python3 src/build_dashboard_data.py     # -> docs/data.js
```

- **Publish the dashboard:** repository Settings → Pages → Branch `main`, folder `/docs`.
- **Real district boundaries (optional):** `python3 src/make_district_map.py <districts.geojson>` writes `docs/districts.js`. Without it the dashboard shows a schematic tile map.

## 7. Limitations

- Effects are associations in survey data, not field-trial results. They show where inputs are likely to pay off; field trials should confirm them.
- Survey plots have no public GPS, so soil and satellite features are district averages.
- Single-plot predictions are noisy, so results are reported per district.
- In a season-by-season test, a district's own past yield predicts its next yield better than the model. The model is for comparing inputs, not for replacing survey estimates.
- 2024 Season B uses only plots with an exact crop share: the NISR screening file lists one crop per plot.
- Perennial crop yields cannot be derived for 2024. Paddy rice is excluded.
- PSTA 5 targets are national annual figures; the dashboard compares them with seasonal district yields for orientation.

## 8. Declaration and acknowledgements

This submission is the team's own work. All data sources are cited above.

AI assistance (Claude, Anthropic) was used to write and debug code, check data processing and draft documentation. The team reviewed the methods and results, and all figures come from running the code in this repository.

**Data:**
- National Institute of Statistics of Rwanda (SAS microdata and tables)
- MINAGRI (PSTA 5)
- iSDA, NASA/USGS (SRTM, MODIS), UCSB Climate Hazards Center (CHIRPS), ECMWF Copernicus (ERA5-Land), ESA Copernicus (Sentinel-1), Google Earth Engine

Intellectual property in this submission is assigned to NISR under the hackathon rules.

**Team:** <name 1, university, student ID> · <name 2, university, student ID>

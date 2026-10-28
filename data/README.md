# Data

Everything in this folder is a district-level aggregate and can be shared. Plot-level microdata are **not** included.

| File | Content |
| --- | --- |
| `sas_district_yield_panel.csv` | NISR SAS published district yields (kg/ha) by crop and season, 2017–2026, with a quality flag. Built from the NISR SAS report tables by `src/build_yield_panel.py` |
| `gee_exports/static_district_features.csv` | Soil pH, organic carbon, nitrogen (iSDAsoil), elevation, slope (SRTM) over district cropland |
| `gee_exports/cropland_area.csv` | District cropland area from a consensus satellite cropland mask |
| `gee_exports/timeseries_<year>.csv` | 16-day NDVI, EVI, rainfall, land temperature, soil moisture, air temperature and Sentinel-1 radar per district and season |
| `model_data/district_crop_summary.csv` | Survey-weighted yield and input adoption (fertilizer, seed, manure, lime, anti-erosion) per district, crop and season, 2022–2025 |
| `model_data/data_dictionary.csv` | Meaning of every model variable |
| `model_outputs/scenario_district.csv` | Yield gain, attainable yield and extra production per district, crop, season and input |
| `model_outputs/scenario_national.csv` | The same, national totals |
| `model_outputs/feature_importance.csv`, `importance_by_crop.csv`, `driver_groups.csv` | SHAP drivers |
| `model_outputs/validation_metrics.csv`, `walk_forward/` | Model validation |
| `model_outputs/dose_response.csv` | Expected yield gain by fertilizer dose and crop |

## Raw data (not included: too large, and governed by NISR access terms)

- **NISR Seasonal Agricultural Survey microdata 2022, 2023, 2024, 2025** (Seasons A, B, C): https://microdata.statistics.gov.rw/index.php/catalog (catalog IDs 103, 111, 113, 124). Register, request access ("Get Microdata"), then unzip each year into `data/microdata/<year>/` as downloaded.
- **NISR SAS report tables 2017–2026:** https://www.statistics.gov.rw (Agriculture → Seasonal Agricultural Survey). Put them in `data/sas_published_tables/` to rebuild the yield panel.
- **Satellite features:** re-extract with the scripts in `gee/` (Google Earth Engine account needed).

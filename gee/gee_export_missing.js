/**************************************************************************************
 * Rwanda harvest early-warning system: satellite feature extraction
 * Paste into the Google Earth Engine Code Editor (https://code.earthengine.google.com).
 *
 * READY-TO-RUN VERSION: exports all missing files using your saved cropland asset
 * (projects/furaha-tasks/assets/rwanda_cropland_20m). Click Run, then RUN every task in the
 * Tasks tab: static_district_features, cropland_area, timeseries_2017..2024 and
 * cultivated_area_<year>_<A|B> for 2019..2026 (26 tasks). Do not cancel them.
 * You already have timeseries_2025 and timeseries_2026 from the new script.
 * (To rebuild the cropland asset from scratch, set STEP = 1.)
 *
 * Exports CSVs to Google Drive folder "rwanda_harvest_ews":
 *   static_district_features.csv  soil pH, organic carbon, nitrogen (iSDAsoil 0-20 cm),
 *                                 elevation, slope, share of cropland on slopes > 16 deg
 *   cropland_area.csv             consensus cropland area (ha) per district (column "sum")
 *   timeseries_<year>.csv         16-day series per district, season and period, over cropland:
 *                                 ndvi, evi (MODIS), rain_mm (CHIRPS), lst_day_c (MODIS),
 *                                 soil_moisture, t2m_c (ERA5-Land), s1_vv_db, s1_vh_db (Sentinel-1)
 *   cultivated_area_<year>_<season>.csv  actively cultivated cropland (ha, column "sum") per
 *                                 district, from Sentinel-2 at 30 m (2019 onward)
 *
 * Seasons follow the NISR Seasonal Agricultural Survey:
 *   Season A = 1 Sep (previous year), 11 periods of 16 days (to ~24 Feb)
 *   Season B = 1 Mar, 8 periods of 16 days (to ~6 Jul)
 *
 * Tip: set YEARS to one year (e.g. [2025]) for a first test run.
 **************************************************************************************/

var STEP = 2;                                  // cropland asset already saved
var CROPLAND_ASSET = 'projects/furaha-tasks/assets/rwanda_cropland_20m';
var YEARS = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024];   // time series to (re)export
var AREA_YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]; // cultivated area
var EXPORT_TIMESERIES = true;                  // set false to export only cultivated area
var EXPORT_AREA = true;                        // Sentinel-2 cultivated area (slowest part)
var LAST_YEAR = 2026, LAST_SEASON = 'B';      // nothing after 2026 Season B
var DRIVE_FOLDER = 'rwanda_harvest_ews';
var SCALE = 250;                               // metres, for time-series means (MODIS native)
var AREA_SCALE = 20;                           // metres, for cropland area
var CULT_SCALE = 30;                           // metres, for cultivated area (lighter, avoids time-outs)
var PERIOD_DAYS = 16;
var SEASONS = {
  A: {month: 9, day: 1, periods: 11, yearOffset: -1},
  B: {month: 3, day: 1, periods: 8,  yearOffset: 0}
};
// Cultivated-area thresholds on Sentinel-2 NDVI within a season (tune against SAS area)
var NDVI_P90_MIN = 0.45, NDVI_RANGE_MIN = 0.20;

/* ---------------------------------------------------------------- districts */
var districts = ee.FeatureCollection('FAO/GAUL/2015/level2')
  .filter(ee.Filter.eq('ADM0_NAME', 'Rwanda'))
  .map(function (f) {
    return f.select(['ADM1_NAME', 'ADM2_NAME'], ['province_gaul', 'district_gaul']);
  });
var region = districts.geometry();
print('Districts (expect 30):', districts.size());
print('District names:', districts.aggregate_array('district_gaul').sort());

Map.centerObject(region, 9);
Map.addLayer(ee.Image().paint(districts, 0, 1), {palette: ['000000']}, 'Districts');

/* ---------------------------------------------------------------- STEP 1: cropland asset */
if (STEP === 1) {
  // A pixel is cropland when at least 2 of 3 open maps agree
  var dea = ee.ImageCollection('projects/sat-io/open-datasets/DEAF/CROPLAND-EXTENT/mask')
    .filterBounds(region).mosaic().select(0).eq(1).unmask(0);
  var worldCover = ee.ImageCollection('ESA/WorldCover/v200').first().select('Map').eq(40).unmask(0);
  var dynWorld = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')
    .filterBounds(region).filterDate('2021-01-01', '2023-01-01')
    .select('label').mode().eq(4).unmask(0);   // 4 = crops
  var consensus = dea.add(worldCover).add(dynWorld).gte(2).rename('cropland').toByte().clip(region);
  Map.addLayer(consensus.selfMask(), {palette: ['#e6a817']}, 'Consensus cropland (preview)');
  Export.image.toAsset({
    image: consensus, description: 'rwanda_cropland_20m', assetId: 'rwanda_cropland_20m',
    region: region.bounds(), scale: AREA_SCALE, maxPixels: 1e10,
    pyramidingPolicy: {cropland: 'mode'}
  });
  print('STEP 1: open the Tasks tab and RUN "rwanda_cropland_20m". Then switch to STEP = 2.');
}

/* ---------------------------------------------------------------- STEP 2 uses the saved mask */
var cropland = ee.Image(CROPLAND_ASSET).select('cropland').selfMask().clip(region);

/* ---------------------------------------------------------------- dynamic layers */
function modisVI(start, end) {
  return ee.ImageCollection('MODIS/061/MOD13Q1').filterDate(start, end)
    .map(function (img) {
      var good = img.select('SummaryQA').lte(1);
      return img.select(['NDVI', 'EVI']).multiply(0.0001).updateMask(good);
    }).mean().rename(['ndvi', 'evi']);
}
function modisLST(start, end) {
  return ee.ImageCollection('MODIS/061/MOD11A2').filterDate(start, end)
    .map(function (img) { return img.select('LST_Day_1km').multiply(0.02).subtract(273.15); })
    .mean().rename('lst_day_c');
}
function chirpsRain(start, end) {
  return ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY').filterDate(start, end)
    .select('precipitation').sum().rename('rain_mm');
}
function era5Land(start, end) {
  var col = ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR').filterDate(start, end);
  return col.select('volumetric_soil_water_layer_1').mean().rename('soil_moisture')
    .addBands(col.select('temperature_2m').mean().subtract(273.15).rename('t2m_c'));
}
function s1Backscatter(start, end) {
  return ee.ImageCollection('COPERNICUS/S1_GRD')
    .filterBounds(region).filterDate(start, end)
    .filter(ee.Filter.eq('instrumentMode', 'IW'))
    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
    .select(['VV', 'VH']).mean().rename(['s1_vv_db', 's1_vh_db']);
}
function periodImage(start, end) {
  return modisVI(start, end)
    .addBands(modisLST(start, end))
    .addBands(chirpsRain(start, end))
    .addBands(era5Land(start, end))
    .addBands(s1Backscatter(start, end));
}

/* ---------------------------------------------------------------- season helpers (client side) */
function iso(d) { return d.toISOString().slice(0, 10); }
function seasonPeriods(year, season) {
  var s = SEASONS[season];
  var t0 = Date.UTC(year + s.yearOffset, s.month - 1, s.day);
  var out = [];
  for (var k = 0; k < s.periods; k++) {
    var a = new Date(t0 + PERIOD_DAYS * k * 864e5);
    var b = new Date(t0 + PERIOD_DAYS * (k + 1) * 864e5);
    out.push({period: k + 1, start: iso(a), end: iso(b)});
  }
  return out;
}
function seasonsFor(year) {
  var list = [];
  ['A', 'B'].forEach(function (s) {
    if (year < LAST_YEAR || (year === LAST_YEAR && s <= LAST_SEASON)) list.push(s);
  });
  return list;
}
function tag(fc, props) {
  return fc.map(function (f) { return f.set(props).setGeometry(null); });
}

/* ---------------------------------------------------------------- tables */
function timeseriesTable(year) {
  var parts = [];
  seasonsFor(year).forEach(function (season) {
    seasonPeriods(year, season).forEach(function (p) {
      var img = periodImage(p.start, p.end).updateMask(cropland);
      var fc = img.reduceRegions({collection: districts, reducer: ee.Reducer.mean(),
                                  scale: SCALE, tileScale: 4});
      parts.push(tag(fc, {year: year, season: season, period: p.period,
                          start: p.start, end: p.end}));
    });
  });
  return ee.FeatureCollection(parts).flatten();
}

function activeCropland(year, season) {
  var ps = seasonPeriods(year, season);
  var start = ps[0].start, end = ps[ps.length - 1].end;
  var cs = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED');
  var ndvi = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(region).filterDate(start, end)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 70))
    .linkCollection(cs, ['cs'])
    .map(function (im) {
      return im.normalizedDifference(['B8', 'B4']).rename('ndvi')
        .updateMask(im.select('cs').gte(0.6));
    });
  var p = ndvi.reduce(ee.Reducer.percentile([10, 90]));
  var p10 = p.select('ndvi_p10'), p90 = p.select('ndvi_p90');
  return p90.gt(NDVI_P90_MIN).and(p90.subtract(p10).gt(NDVI_RANGE_MIN))
    .updateMask(cropland).unmask(0).rename('active');
}

function cultivatedAreaTable(year, season) {
  var img = activeCropland(year, season).multiply(ee.Image.pixelArea().divide(1e4));
  var fc = img.reduceRegions({collection: districts, reducer: ee.Reducer.sum(),
                              scale: CULT_SCALE, tileScale: 16});
  return tag(fc, {year: year, season: season});
}

function isda(name) { return ee.Image('ISDASOIL/Africa/v1/' + name).select('mean_0_20'); }
var dem = ee.Image('USGS/SRTMGL1_003');
var slope = ee.Terrain.slope(dem);
var staticImg = isda('ph').divide(10).rename('soil_ph')                                  // pH = x/10
  .addBands(isda('carbon_organic').divide(10).exp().subtract(1).rename('soil_org_carbon_gkg'))  // exp(x/10)-1
  .addBands(isda('nitrogen_total').divide(100).exp().subtract(1).rename('soil_nitrogen_gkg'))   // exp(x/100)-1
  .addBands(dem.rename('elevation_m'))
  .addBands(slope.rename('slope_deg'))
  .addBands(slope.gt(16).rename('share_slope_gt16deg'))
  .updateMask(cropland);
var staticTable = tag(staticImg.reduceRegions({collection: districts, reducer: ee.Reducer.mean(),
                                               scale: SCALE, tileScale: 4}), {});
var croplandAreaTable = tag(cropland.unmask(0).multiply(ee.Image.pixelArea().divide(1e4))
  .reduceRegions({collection: districts, reducer: ee.Reducer.sum(), scale: AREA_SCALE,
                  tileScale: 8}), {});

/* ---------------------------------------------------------------- STEP 2: quick look + exports */
function exportCSV(fc, name) {
  Export.table.toDrive({collection: fc, description: name, folder: DRIVE_FOLDER,
                        fileNamePrefix: name, fileFormat: 'CSV'});
}
if (STEP === 2) {
  Map.addLayer(cropland, {palette: ['#e6a817']}, 'Consensus cropland (asset)');
  Map.addLayer(activeCropland(2025, 'A').selfMask(), {palette: ['#1a9850']},
               'Actively cultivated, Season A 2025', false);
  print('Static features (first rows):', staticTable.limit(3));

  exportCSV(staticTable, 'static_district_features');
  exportCSV(croplandAreaTable, 'cropland_area');
  if (EXPORT_TIMESERIES) YEARS.forEach(function (y) {
    exportCSV(timeseriesTable(y), 'timeseries_' + y);
  });
  if (EXPORT_AREA) AREA_YEARS.forEach(function (y) {
    seasonsFor(y).forEach(function (s) {
      exportCSV(cultivatedAreaTable(y, s), 'cultivated_area_' + y + '_' + s);
    });
  });
  print('RUN every task in the Tasks tab and do not cancel them. Download from Drive only when all show a tick.');
}

"""
Turn a Rwanda district boundary file into docs/districts.js, so the dashboard draws real district maps
instead of the schematic tile map.

1. Download district (ADM2) boundaries as GeoJSON, for example:
     geoBoundaries  https://www.geoboundaries.org  -> Rwanda, ADM2, "geoBoundaries-RWA-ADM2_simplified.geojson"
     or HDX         https://data.humdata.org/dataset/cod-ab-rwa (district layer, GeoJSON)
   A shapefile also works if geopandas is installed.
2. Run from the repository root:
     python3 src/make_district_map.py data/boundaries/geoBoundaries-RWA-ADM2_simplified.geojson
"""
import json
import re
import sys
from pathlib import Path

DISTRICTS = ["Bugesera", "Burera", "Gakenke", "Gasabo", "Gatsibo", "Gicumbi", "Gisagara", "Huye", "Kamonyi",
             "Karongi", "Kayonza", "Kicukiro", "Kirehe", "Muhanga", "Musanze", "Ngoma", "Ngororero", "Nyabihu",
             "Nyagatare", "Nyamagabe", "Nyamasheke", "Nyanza", "Nyarugenge", "Nyaruguru", "Rubavu", "Ruhango",
             "Rulindo", "Rusizi", "Rutsiro", "Rwamagana"]
KEY = {re.sub(r"[^a-z]", "", d.lower()): d for d in DISTRICTS}
KEY.update({"nyarugenege": "Nyarugenge", "cyangugu": "Rusizi", "gisenyi": "Rubavu", "ruhengeri": "Musanze"})


def load(path):
    p = Path(path)
    if p.suffix.lower() in (".geojson", ".json"):
        return json.load(open(p, encoding="utf-8"))["features"]
    import geopandas as gpd  # shapefile or other formats
    g = gpd.read_file(p).to_crs(4326)
    return json.loads(g.to_json())["features"]


def district_of(props):
    for v in props.values():
        k = re.sub(r"[^a-z]", "", str(v).lower())
        if k in KEY:
            return KEY[k]
    return None


def simplify(ring, tol):
    """Douglas-Peucker on a list of [lon, lat]."""
    if len(ring) < 5:
        return ring
    def dist(p, a, b):
        (x, y), (x1, y1), (x2, y2) = p, a, b
        dx, dy = x2 - x1, y2 - y1
        if dx == dy == 0:
            return ((x - x1) ** 2 + (y - y1) ** 2) ** .5
        t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
        return ((x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2) ** .5
    keep, stack = {0, len(ring) - 1}, [(0, len(ring) - 1)]
    while stack:
        i, j = stack.pop()
        best, idx = 0, None
        for k in range(i + 1, j):
            dd = dist(ring[k], ring[i], ring[j])
            if dd > best:
                best, idx = dd, k
        if idx is not None and best > tol:
            keep.add(idx)
            stack += [(i, idx), (idx, j)]
    return [ring[k] for k in sorted(keep)]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = sys.argv[1]
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("docs/districts.js")
    tol = 0.002  # degrees, about 200 m
    geo, unmatched = {}, []
    for f in load(src):
        d = district_of(f.get("properties", {}))
        if not d:
            unmatched.append(f.get("properties", {}))
            continue
        gm = f["geometry"]
        polys = gm["coordinates"] if gm["type"] == "MultiPolygon" else [gm["coordinates"]]
        for poly in polys:
            ring = simplify([[round(x, 4), round(y, 4)] for x, y in poly[0]], tol)
            if len(ring) >= 4:
                geo.setdefault(d, []).append(ring)
    missing = sorted(set(DISTRICTS) - set(geo))
    out.write_text("window.DIST_GEO = " + json.dumps({"source": Path(src).name, "districts": geo},
                                                      separators=(",", ":")) + ";\n")
    print(f"Wrote {out}: {len(geo)} districts, {sum(len(r) for v in geo.values() for r in v):,} points")
    if missing:
        print("WARNING districts not found in the file:", missing)
    if unmatched:
        print(f"{len(unmatched)} features skipped (no district name matched), e.g. {unmatched[0]}")


if __name__ == "__main__":
    main()

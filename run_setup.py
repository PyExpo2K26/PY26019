"""
run_setup.py  —  One-time basin setup for all cities that have dem_raw.tif
Run this ONCE from your project root:   python run_setup.py

It will:
  1. Find every city folder that has dem_raw.tif
  2. Run the full GIS pipeline (fill depressions → flow dir → flow acc → streams → watershed → HAND)
  3. Save all derived files in the same city folder
  4. Skip cities that are already fully set up
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'utils'))

# City bounding boxes (west, south, east, north)
# Only the 4 cities you have DEM files for
CITY_BOUNDS = {
    'chennai':  (79.9, 12.8, 80.5, 13.4),
    'kolkata':  (88.1, 22.3, 88.6, 22.8),
    'guwahati': (91.5, 25.9, 92.0, 26.3),
    'kochi':    (76.1,  9.8, 76.5, 10.2),
}

# Pour points (lon, lat) — stream outlet for watershed delineation
POUR_POINTS = {
    'chennai':  (80.28, 13.08),
    'kolkata':  (88.35, 22.55),
    'guwahati': (91.75, 26.10),
    'kochi':    (76.25, 10.00),
}

WORKSPACE = 'hydro_data'


def city_status(city):
    """Return dict of which files exist for a city."""
    base = os.path.join(WORKSPACE, city)
    return {
        'dem_raw':    os.path.exists(os.path.join(base, 'dem_raw.tif')),
        'dem_filled': os.path.exists(os.path.join(base, 'dem_filled.tif')),
        'streams':    os.path.exists(os.path.join(base, 'streams.shp')),
        'watershed':  os.path.exists(os.path.join(base, 'watershed.shp')),
        'hand':       os.path.exists(os.path.join(base, 'hand.tif')),
    }


def is_ready(city):
    s = city_status(city)
    return s['dem_filled'] and s['streams'] and s['hand']


def setup_city(city):
    """Run full GIS pipeline for a single city."""
    bounds     = CITY_BOUNDS[city]
    pour_point = POUR_POINTS.get(city)
    workspace  = os.path.join(WORKSPACE, city)
    os.makedirs(workspace, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Setting up: {city.upper()}")
    print(f"  Workspace:  {os.path.abspath(workspace)}")
    print(f"{'='*60}")

    try:
        from hydro_terrain import TerrainProcessor
        from hydro_flood_simulation import FloodSimulator

        terrain  = TerrainProcessor(output_dir=workspace)
        flood_sim = FloodSimulator()

        dem_raw    = os.path.join(workspace, 'dem_raw.tif')
        dem_filled = os.path.join(workspace, 'dem_filled.tif')
        fdir_path  = os.path.join(workspace, 'dem_flowdir.tif')
        facc_path  = os.path.join(workspace, 'dem_flowacc.tif')
        streams    = os.path.join(workspace, 'streams.shp')
        watershed  = os.path.join(workspace, 'watershed.shp')
        hand_path  = os.path.join(workspace, 'hand.tif')

        # ── 1. Fill depressions ──────────────────────────────────
        if not os.path.exists(dem_filled):
            print("[1/6] Filling depressions...")
            terrain.fill_depressions(dem_raw, dem_filled)
        else:
            print("[1/6] dem_filled.tif already exists — skipping")

        # ── 2. Flow direction ────────────────────────────────────
        if not os.path.exists(fdir_path):
            print("[2/6] Calculating flow direction...")
            terrain.calculate_flow_direction(dem_filled, fdir_path)
        else:
            print("[2/6] dem_flowdir.tif already exists — skipping")

        # ── 3. Flow accumulation ─────────────────────────────────
        if not os.path.exists(facc_path):
            print("[3/6] Calculating flow accumulation...")
            terrain.calculate_flow_accumulation(fdir_path, facc_path)
        else:
            print("[3/6] dem_flowacc.tif already exists — skipping")

        # ── 4. Extract streams ───────────────────────────────────
        if not os.path.exists(streams):
            print("[4/6] Extracting stream network (threshold=500)...")
            result = terrain.extract_stream_network(facc_path, threshold=500, output_path=streams)
            if result is None:
                print("  Threshold 500 produced no streams. Trying 100...")
                terrain.extract_stream_network(facc_path, threshold=100, output_path=streams)
        else:
            print("[4/6] streams.shp already exists — skipping")

        # ── 5. Delineate watershed ───────────────────────────────
        if not os.path.exists(watershed):
            print("[5/6] Delineating watershed...")
            if pour_point:
                try:
                    terrain.delineate_watershed(fdir_path, pour_point, watershed)
                except Exception as e:
                    print(f"  Watershed failed: {e} — continuing without it")
            else:
                print("  No pour point defined — skipping watershed")
        else:
            print("[5/6] watershed.shp already exists — skipping")

        # ── 6. Calculate HAND ────────────────────────────────────
        if not os.path.exists(hand_path):
            print("[6/6] Calculating HAND (Height Above Nearest Drainage)...")
            if os.path.exists(streams):
                flood_sim.calculate_hand(dem_filled, streams, hand_path)
            else:
                print("  streams.shp missing — cannot calculate HAND")
        else:
            print("[6/6] hand.tif already exists — skipping")

        # ── Summary ──────────────────────────────────────────────
        status = city_status(city)
        ready  = status['dem_filled'] and status['streams'] and status['hand']
        print(f"\n  {'✓ COMPLETE' if ready else '⚠ PARTIAL'} — {city.upper()}")
        for k, v in status.items():
            print(f"    {'✓' if v else '✗'} {k}")
        return ready

    except ImportError as e:
        print(f"\n  ✗ Import error: {e}")
        print("  Make sure utils/ contains hydro_terrain.py and hydro_flood_simulation.py")
        print("  Also install: pip install pysheds rasterio geopandas rasterstats scipy shapely")
        return False
    except Exception as e:
        print(f"\n  ✗ Error: {e}")
        import traceback; traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("  FLOOD PREDICTION — BASIN SETUP")
    print("=" * 60)

    # Find all cities with dem_raw.tif
    cities_with_dem = []
    cities_missing  = []

    for city in CITY_BOUNDS:
        dem_path = os.path.join(WORKSPACE, city, 'dem_raw.tif')
        if os.path.exists(dem_path):
            if is_ready(city):
                print(f"  ✓ {city:12s} — already fully set up")
            else:
                cities_with_dem.append(city)
                print(f"  → {city:12s} — dem_raw.tif found, needs processing")
        else:
            cities_missing.append(city)
            print(f"  ✗ {city:12s} — dem_raw.tif not found")

    if not cities_with_dem:
        print("\nNo cities need processing. All done!")
        return

    print(f"\nWill process {len(cities_with_dem)} cities: {', '.join(cities_with_dem)}")
    print("This may take several minutes per city depending on DEM size.")

    results = {}
    for city in cities_with_dem:
        results[city] = setup_city(city)

    # Final report
    print("\n" + "=" * 60)
    print("  SETUP COMPLETE — SUMMARY")
    print("=" * 60)
    for city, ok in results.items():
        print(f"  {'✓' if ok else '✗'} {city}: {'Ready' if ok else 'Incomplete — check errors above'}")

    if cities_missing:
        print(f"\nCities still missing dem_raw.tif:")
        for city in cities_missing:
            path = os.path.join(WORKSPACE, city, 'dem_raw.tif')
            print(f"  → Place DEM at: {os.path.abspath(path)}")

    print("\nNow restart Flask and use the Hydrology page!")


if __name__ == '__main__':
    main()
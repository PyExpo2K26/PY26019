# ═══════════════════════════════════════════════════════════════════════════
# TERRAIN PREPROCESSING MODULE (WINDOWS COMPATIBLE - NO ELEVATION PACKAGE)
# ═══════════════════════════════════════════════════════════════════════════

"""
This module handles DEM preprocessing and watershed delineation.

CORRECTED VERSION: 
- No richdem dependency (uses pysheds instead)
- No elevation package (manual download instead - Windows compatible)
- Fixed polygonize() tuple unpacking bug
"""

import os
import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.warp import calculate_default_transform, reproject, Resampling
import geopandas as gpd
from shapely.geometry import box, Point, shape
# elevation package removed - causes issues on Windows
from pysheds.grid import Grid

class TerrainProcessor:
    """
    Handles DEM preprocessing and watershed delineation.
    Windows-compatible version.
    """
    
    def __init__(self, output_dir='hydro_data'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def download_dem(self, bounds, output_file='dem_raw.tif'):
        """
        Download SRTM DEM for a bounding box.
        
        WINDOWS VERSION: Manual download required.
        The elevation package has compatibility issues on Windows.
        
        Args:
            bounds: tuple (west, south, east, north) in decimal degrees
            output_file: where to save the DEM
        
        Returns:
            path to DEM file (if exists)
        """
        output_path = os.path.join(self.output_dir, output_file)
        
        # Check if DEM already exists
        if os.path.exists(output_path):
            print(f"✓ Using existing DEM: {output_path}")
            return output_path
        
        # If not, provide manual download instructions
        print("\n" + "="*70)
        print("DEM MANUAL DOWNLOAD REQUIRED")
        print("="*70)
        print(f"\nThe automatic download has Windows compatibility issues.")
        print(f"Please download DEM manually using one of these methods:")
        print("\n" + "-"*70)
        print("METHOD 1: OpenTopography (EASIEST)")
        print("-"*70)
        print("1. Go to: https://portal.opentopography.org/raster?opentopoID=OTSRTM.082015.4326.1")
        print("2. On the map, click 'Select a Region'")
        print(f"3. Draw a box covering: West={bounds[0]}, South={bounds[1]}, East={bounds[2]}, North={bounds[3]}")
        print("4. Click 'Submit'")
        print("5. Select 'GeoTIFF' as output format")
        print("6. Click 'Download'")
        print(f"7. Save/rename the downloaded file to: {output_path}")
        print("\n" + "-"*70)
        print("METHOD 2: USGS Earth Explorer")
        print("-"*70)
        print("1. Go to: https://earthexplorer.usgs.gov/")
        print("2. Create free account / Login")
        print("3. Enter coordinates:")
        print(f"   - Decimal: West={bounds[0]}, South={bounds[1]}, East={bounds[2]}, North={bounds[3]}")
        print("4. Click 'Data Sets' → Expand 'Digital Elevation' → Check 'SRTM 1 Arc-Second Global'")
        print("5. Click 'Results'")
        print("6. Click download icon → Choose 'GeoTIFF 1 Arc-second'")
        print(f"7. Save to: {output_path}")
        print("\n" + "-"*70)
        print("METHOD 3: Use Sample DEM (For Testing)")
        print("-"*70)
        print("If you just want to test the system, you can:")
        print("1. Download any SRTM DEM for your area from Google")
        print(f"2. Save it as: {output_path}")
        print("="*70)
        
        # Check if file was created during instructions
        if os.path.exists(output_path):
            print(f"\n✓ DEM found: {output_path}")
            return output_path
        
        # Return path anyway so user knows where to save it
        print(f"\n  Waiting for DEM file at: {output_path}")
        print("After downloading, rerun the setup.")
        return output_path
    
    def fill_depressions(self, dem_path, output_path=None):
        """
        Fill sinks/depressions in DEM (required for flow routing).
        Water gets stuck in depressions causing routing errors.
        
        Uses pysheds instead of richdem (Windows compatible).
        """
        if output_path is None:
            output_path = dem_path.replace('.tif', '_filled.tif')
        
        # Check if input DEM exists
        if not os.path.exists(dem_path):
            print(f"  Input DEM not found: {dem_path}")
            print("Please download DEM first using download_dem()")
            return output_path
        
        print("Filling depressions using pysheds...")
        
        try:
            # Load DEM with pysheds
            grid = Grid.from_raster(dem_path)
            dem = grid.read_raster(dem_path)
            
            # Fill pits (small depressions)
            pit_filled_dem = grid.fill_pits(dem)
            
            # Fill depressions (larger low areas)
            flooded_dem = grid.fill_depressions(pit_filled_dem)
            
            # Save filled DEM
            grid.to_raster(flooded_dem, output_path)
            
            print(f"✓ Filled DEM saved: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"  Depression filling failed: {e}")
            print("Using unfilled DEM - this may cause minor artifacts")
            
            # Fallback: just copy the file
            import shutil
            shutil.copy(dem_path, output_path)
            print(f"✓ DEM copied (unfilled): {output_path}")
            return output_path
    
    def calculate_flow_direction(self, dem_path, output_path=None):
        """
        Calculate D8 flow direction from DEM.
        Each cell flows to one of 8 neighbors (N, NE, E, SE, S, SW, W, NW).
        """
        if output_path is None:
            output_path = dem_path.replace('.tif', '_flowdir.tif')
        
        # Check if input exists
        if not os.path.exists(dem_path):
            print(f"  Input DEM not found: {dem_path}")
            return output_path
        
        print("Calculating flow direction...")
        
        try:
            grid = Grid.from_raster(dem_path)
            dem = grid.read_raster(dem_path)
            
            # Fill depressions
            pit_filled_dem = grid.fill_pits(dem)
            flooded_dem = grid.fill_depressions(pit_filled_dem)
            
            # Resolve flats
            inflated_dem = grid.resolve_flats(flooded_dem)
            
            # Calculate flow direction (D8)
            fdir = grid.flowdir(inflated_dem, dirmap=(64, 128, 1, 2, 4, 8, 16, 32))
            
            # Save
            grid.to_raster(fdir, output_path)
            
            print(f"✓ Flow direction saved: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"✗ Flow direction calculation failed: {e}")
            raise
    
    def calculate_flow_accumulation(self, fdir_path, output_path=None):
        """
        Calculate flow accumulation (how many cells flow into each cell).
        High values = rivers/streams.
        """
        if output_path is None:
            output_path = fdir_path.replace('_flowdir.tif', '_flowacc.tif')
        
        # Check if input exists
        if not os.path.exists(fdir_path):
            print(f"  Flow direction file not found: {fdir_path}")
            return output_path
        
        print("Calculating flow accumulation...")
        
        try:
            grid = Grid.from_raster(fdir_path)
            fdir = grid.read_raster(fdir_path)
            
            # Calculate accumulation
            acc = grid.accumulation(fdir, dirmap=(64, 128, 1, 2, 4, 8, 16, 32))
            
            # Save
            grid.to_raster(acc, output_path)
            
            print(f"✓ Flow accumulation saved: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"✗ Flow accumulation calculation failed: {e}")
            raise
    
    def delineate_watershed(self, fdir_path, pour_point, output_path=None):
        """
        Delineate watershed boundary from a pour point (outlet location).
        
        Args:
            fdir_path: flow direction raster
            pour_point: (x, y) coordinates in same CRS as DEM
            output_path: where to save watershed shapefile
        
        Returns:
            GeoDataFrame with watershed polygon
        """
        if output_path is None:
            output_path = os.path.join(self.output_dir, 'watershed.shp')
        
        # Check if input exists
        if not os.path.exists(fdir_path):
            print(f"  Flow direction file not found: {fdir_path}")
            return None
        
        print(f"Delineating watershed from pour point: {pour_point}")
        
        try:
            grid = Grid.from_raster(fdir_path)
            fdir = grid.read_raster(fdir_path)
            
            # Snap pour point to high accumulation cell
            x, y = pour_point
            x_snap, y_snap = grid.snap_to_mask(
                grid.accumulation(fdir, dirmap=(64, 128, 1, 2, 4, 8, 16, 32)) > 1000,
                (x, y)
            )
            
            # Delineate catchment
            catch = grid.catchment(
                x=x_snap, y=y_snap, fdir=fdir,
                dirmap=(64, 128, 1, 2, 4, 8, 16, 32),
                xytype='coordinate'
            )
            
            # FIX: polygonize() returns (geometry_dict, value) tuples
            shapes_gen = grid.polygonize(catch)
            geometries = []
            for geom_dict, value in shapes_gen:
                if value > 0:
                    geometries.append(shape(geom_dict))
            
            if not geometries:
                print("  Warning: No watershed geometry found. Check pour point coordinates.")
                return None
            
            # Save as shapefile
            gdf = gpd.GeoDataFrame(geometry=geometries, crs=grid.crs)
            gdf.to_file(output_path)
            
            print(f"✓ Watershed saved: {output_path}")
            return gdf
            
        except Exception as e:
            print(f"✗ Watershed delineation failed: {e}")
            raise
    
    def extract_stream_network(self, flowacc_path, threshold=1000, output_path=None):
        """
        Extract stream network from flow accumulation.
        
        Args:
            flowacc_path: flow accumulation raster
            threshold: minimum accumulation to be considered a stream
            output_path: where to save stream shapefile
        """
        if output_path is None:
            output_path = os.path.join(self.output_dir, 'streams.shp')
        
        # Check if input exists
        if not os.path.exists(flowacc_path):
            print(f"  Flow accumulation file not found: {flowacc_path}")
            return None
        
        print(f"Extracting streams (threshold: {threshold} cells)")
        
        try:
            grid = Grid.from_raster(flowacc_path)
            acc = grid.read_raster(flowacc_path)
            
            # Threshold to get streams
            streams = acc > threshold
            
            # FIX: polygonize() returns (geometry_dict, value) tuples — not bare geometries
            shapes_gen = grid.polygonize(streams)
            geometries = []
            for geom_dict, value in shapes_gen:
                if value > 0:  # Only keep stream cells
                    geometries.append(shape(geom_dict))
            
            if not geometries:
                print(f"  Warning: No streams found at threshold={threshold}. Try lowering the threshold.")
                return None
            
            gdf = gpd.GeoDataFrame(geometry=geometries, crs=grid.crs)
            gdf.to_file(output_path)
            
            print(f"✓ Streams saved: {output_path} ({len(geometries)} features)")
            return gdf
            
        except Exception as e:
            print(f"✗ Stream extraction failed: {e}")
            raise


# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Test the terrain processor.
    Run this file directly to test: python hydro_terrain.py
    """
    
    print("="*70)
    print("TERRAIN PROCESSOR TEST")
    print("="*70)
    
    # Example: Process terrain for Mumbai region
    processor = TerrainProcessor(output_dir='hydro_data/mumbai')
    
    # Define bounding box (west, south, east, north)
    mumbai_bounds = (72.7, 18.8, 73.1, 19.3)
    
    print("\nThis will show you how to manually download DEM data.")
    print("The automatic download doesn't work on Windows.")
    
    try:
        # Download DEM (shows manual instructions)
        print("\n" + "="*70)
        print("STEP 1: Download DEM")
        print("="*70)
        dem_path = processor.download_dem(mumbai_bounds)
        
        # Check if DEM exists before continuing
        if not os.path.exists(dem_path):
            print("\n" + "="*70)
            print("  DEM file not found!")
            print("="*70)
            print(f"Please download DEM and save to: {dem_path}")
            print("Then run this script again.")
            exit(0)
        
        # Fill depressions
        print("\n" + "="*70)
        print("STEP 2: Fill depressions")
        print("="*70)
        filled_dem = processor.fill_depressions(dem_path)
        
        # Calculate flow direction
        print("\n" + "="*70)
        print("STEP 3: Calculate flow direction")
        print("="*70)
        fdir_path = processor.calculate_flow_direction(filled_dem)
        
        # Calculate flow accumulation
        print("\n" + "="*70)
        print("STEP 4: Calculate flow accumulation")
        print("="*70)
        flowacc_path = processor.calculate_flow_accumulation(fdir_path)
        
        # Extract stream network
        print("\n" + "="*70)
        print("STEP 5: Extract stream network")
        print("="*70)
        streams = processor.extract_stream_network(flowacc_path, threshold=500)
        
        # Delineate watershed
        print("\n" + "="*70)
        print("STEP 6: Delineate watershed")
        print("="*70)
        pour_point = (72.9, 19.0)  # example coordinates
        watershed = processor.delineate_watershed(fdir_path, pour_point)
        
        print("\n" + "="*70)
        print("✓ TERRAIN PREPROCESSING COMPLETE!")
        print("="*70)
        print(f"\nGenerated files in: {processor.output_dir}")
        print("- dem_raw.tif")
        print("- dem_filled.tif")
        print("- dem_flowdir.tif")
        print("- dem_flowacc.tif")
        print("- streams.shp")
        print("- watershed.shp")
        print("\nYou can now use these files for flood modeling!")
        
    except Exception as e:
        print("\n" + "="*70)
        print("✗ ERROR")
        print("="*70)
        print(f"Error: {e}")
        print("\nCommon issues:")
        print("1. DEM file not downloaded - follow the manual download instructions")
        print("2. pysheds not installed: pip install pysheds")
        print("3. geopandas not installed: pip install geopandas")
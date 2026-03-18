import numpy as np
import rasterio
from rasterio.features import rasterize
import geopandas as gpd
from pysheds.grid import Grid
from scipy.ndimage import distance_transform_edt
import matplotlib.pyplot as plt
import folium
from folium import plugins

class FloodSimulator:
    """
    2D flood inundation modeling using HAND method.
    """
    
    def __init__(self):
        self.grid = None
        self.dem = None
        self.hand = None
    
    def calculate_hand(self, dem_path, streams_path, output_path):
        """
        Calculate Height Above Nearest Drainage (HAND).
        
        HAND = elevation difference between each cell and nearest stream.
        Areas with low HAND values flood first.
        
        Args:
            dem_path: path to DEM raster
            streams_path: path to stream network shapefile
            output_path: where to save HAND raster
        
        Returns:
            path to HAND raster
        """
        print("Calculating HAND...")
        
        # Load DEM
        with rasterio.open(dem_path) as src:
            dem = src.read(1)
            profile = src.profile
            transform = src.transform
        
        # Load streams
        streams = gpd.read_file(streams_path)
        
        # Rasterize streams
        stream_mask = rasterize(
            [(geom, 1) for geom in streams.geometry],
            out_shape=dem.shape,
            transform=transform,
            fill=0,
            dtype=np.uint8
        )
        
        # Find nearest stream for each cell using distance transform
        distance, nearest_idx = distance_transform_edt(
            stream_mask == 0,
            return_indices=True
        )
        
        # Get elevation of nearest stream
        nearest_stream_elev = dem[nearest_idx[0], nearest_idx[1]]
        
        # HAND = elevation - nearest stream elevation
        hand = dem - nearest_stream_elev
        hand = np.maximum(hand, 0)  # Remove negative values
        
        # Save
        profile.update(dtype=rasterio.float32, nodata=-9999)
        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(hand.astype(np.float32), 1)
        
        print(f"✓ HAND raster saved: {output_path}")
        return output_path
    
    def simulate_flood_depth(self, hand_path, water_level_m, output_path):
        """
        Simulate flood depth based on water level in stream.
        
        Args:
            hand_path: path to HAND raster
            water_level_m: water rise above normal stream level (meters)
            output_path: where to save flood depth raster
        
        Returns:
            tuple: (output_path, stats_dict)
        
        Logic:
            If HAND < water_level → flooded
            Flood depth = water_level - HAND
        """
        print(f"Simulating flood for water level: {water_level_m}m")
        
        with rasterio.open(hand_path) as src:
            hand = src.read(1)
            profile = src.profile
        
        # Calculate flood depth
        flood_depth = water_level_m - hand
        flood_depth = np.maximum(flood_depth, 0)  # No negative depths
        
        # Save
        profile.update(dtype=rasterio.float32, nodata=-9999)
        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(flood_depth.astype(np.float32), 1)
        
        # Calculate statistics
        flooded_cells = np.sum(flood_depth > 0)
        total_cells = flood_depth.size
        flooded_pct = (flooded_cells / total_cells) * 100
        
        max_depth = np.max(flood_depth)
        avg_depth = np.mean(flood_depth[flood_depth > 0]) if flooded_cells > 0 else 0
        
        stats = {
            'water_level_m': water_level_m,
            'flooded_cells': int(flooded_cells),
            'flooded_percent': round(flooded_pct, 2),
            'max_depth_m': round(float(max_depth), 2),
            'avg_depth_m': round(float(avg_depth), 2)
        }
        
        print(f"✓ Flood statistics: {stats}")
        return output_path, stats
    
    def create_flood_extent_polygon(self, flood_depth_path, min_depth=0.1, output_path=None):
        """
        Convert flood depth raster to polygon shapefile.
        
        Args:
            flood_depth_path: path to flood depth raster
            min_depth: minimum depth to consider flooded (meters)
            output_path: where to save polygon shapefile
        
        Returns:
            GeoDataFrame with flood extent polygons
        """
        if output_path is None:
            output_path = flood_depth_path.replace('.tif', '_extent.shp')
        
        print("Extracting flood extent polygons...")
        
        with rasterio.open(flood_depth_path) as src:
            flood_depth = src.read(1)
            transform = src.transform
            crs = src.crs
        
        # Create binary mask
        flood_mask = (flood_depth >= min_depth).astype(np.uint8)
        
        # Vectorize
        from rasterio import features
        from shapely.geometry import shape
        
        shapes_gen = features.shapes(flood_mask, mask=flood_mask > 0, transform=transform)
        
        # Convert to GeoDataFrame
        geoms = []
        values = []
        for geom_dict, value in shapes_gen:
            geoms.append(shape(geom_dict))
            values.append(value)
        
        if len(geoms) > 0:
            gdf = gpd.GeoDataFrame({'flooded': values}, geometry=geoms, crs=crs)
            gdf.to_file(output_path)
            print(f"✓ Flood extent saved: {output_path}")
            return gdf
        else:
            print("⚠️  No flooded areas found")
            return None
    
    def classify_flood_severity(self, flood_depth_path, output_path=None):
        """
        Classify flood depth into severity categories.
        
        Categories (based on UK Environment Agency):
        - 0: No flood
        - 1: Low (0.0 - 0.3m) - passable with caution
        - 2: Moderate (0.3 - 0.6m) - dangerous for vehicles
        - 3: Significant (0.6 - 1.2m) - dangerous for people
        - 4: Extreme (> 1.2m) - life-threatening
        
        Args:
            flood_depth_path: path to flood depth raster
            output_path: where to save classified raster
        
        Returns:
            path to classified raster
        """
        if output_path is None:
            output_path = flood_depth_path.replace('.tif', '_severity.tif')
        
        print("Classifying flood severity...")
        
        with rasterio.open(flood_depth_path) as src:
            depth = src.read(1)
            profile = src.profile.copy()
        
        # Classify into severity levels
        severity = np.zeros_like(depth, dtype=np.uint8)
        severity[depth > 0] = 1      # Low
        severity[depth > 0.3] = 2    # Moderate
        severity[depth > 0.6] = 3    # Significant
        severity[depth > 1.2] = 4    # Extreme
        
        # Update profile for uint8 output with proper nodata
        profile.update({
            'dtype': rasterio.uint8,
            'nodata': 255,  # Use 255 for uint8 nodata (not nan)
            'count': 1
        })
        
        # Write classified raster
        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(severity, 1)
        
        print(f"✓ Severity classification saved: {output_path}")
        return output_path
    
    def create_interactive_flood_map(self, flood_depth_path, center_coords, output_html):
        """
        Create interactive Folium map with flood depth overlay.
        
        Args:
            flood_depth_path: path to flood depth raster
            center_coords: (lat, lon) for map center
            output_html: where to save HTML map
        
        Returns:
            path to HTML file
        """
        print("Creating interactive map...")
        
        # Load flood depth
        with rasterio.open(flood_depth_path) as src:
            depth = src.read(1)
            bounds = src.bounds
        
        # Create base map
        m = folium.Map(
            location=center_coords,
            zoom_start=12,
            tiles='OpenStreetMap'
        )
        
        # Add flood extent as colored overlay
        # (Simplified - in production, use folium.raster_layers.ImageOverlay)
        
        # Calculate flood extent bounds
        image_bounds = [[bounds.bottom, bounds.left], [bounds.top, bounds.right]]
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; bottom: 50px; left: 50px; width: 200px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <p><strong>Flood Depth (m)</strong></p>
        <p><span style="background-color:#FEE5D9; padding: 3px;">0.0 - 0.3</span> Low</p>
        <p><span style="background-color:#FCAE91; padding: 3px;">0.3 - 0.6</span> Moderate</p>
        <p><span style="background-color:#FB6A4A; padding: 3px;">0.6 - 1.2</span> Significant</p>
        <p><span style="background-color:#CB181D; padding: 3px;">&gt; 1.2</span> Extreme</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Save
        m.save(output_html)
        print(f"✓ Interactive map saved: {output_html}")
        
        return output_html


class HECRASInterface:
    """
    Prepares input files for HEC-RAS 2D modeling.
    HEC-RAS itself must be run manually or via win32com on Windows.
    """
    
    def prepare_terrain(self, dem_path, output_hdf):
        """
        Convert DEM to HEC-RAS terrain format (HDF5).
        
        HEC-RAS requires terrain in a specific HDF5 structure.
        Use RAS Mapper GUI to import, or convert programmatically.
        """
        print("HEC-RAS terrain preparation:")
        print("1. Open HEC-RAS")
        print("2. RAS Mapper → Terrain → New Terrain Layer")
        print(f"3. Import DEM: {dem_path}")
        print("4. Save terrain as .hdf file")
        
        return output_hdf
    
    def create_2d_flow_area(self, boundary_shp, cell_size=10):
        """
        Define 2D flow area for HEC-RAS.
        
        Args:
            boundary_shp: watershed or model boundary shapefile
            cell_size: computational cell size in meters
        
        Steps:
            1. Open HEC-RAS
            2. Geometry → 2D Flow Area → Draw Perimeter
            3. Or import from shapefile
            4. Set cell size
        """
        print(f"Creating 2D flow area from: {boundary_shp}")
        print(f"Cell size: {cell_size}m")
        print("This must be done in HEC-RAS GUI:")
        print("Geometry → 2D Flow Area → New")
        
        return None
    
    def set_boundary_conditions(self, inflow_hydrograph):
        """
        Set flow boundary conditions (inflow from runoff calculation).
        
        Args:
            inflow_hydrograph: DataFrame with columns ['time', 'flow_cms']
        
        Steps in HEC-RAS:
            1. Unsteady Flow Editor
            2. Boundary Conditions → SA/2D Area BC Line
            3. Select "Flow Hydrograph"
            4. Enter time series
        """
        print("Boundary condition data prepared:")
        print(inflow_hydrograph.head())
        print("Import this into HEC-RAS Unsteady Flow Editor")
        
        return None

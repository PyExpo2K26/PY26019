import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd
from rasterio.features import rasterize
from rasterstats import zonal_stats
import xarray as xr
from datetime import datetime, timedelta

class RainfallRunoffModel:
    """
    SCS Curve Number method for converting rainfall to runoff.
    """
    
    def __init__(self):
        # Curve numbers for different land use + soil combinations
        # Source: USDA TR-55 handbook
        self.curve_numbers = {
            # Format: (land_use, soil_group): curve_number
            ('forest', 'A'): 36,      # A = sandy soil (high infiltration)
            ('forest', 'B'): 60,      # B = loamy soil
            ('forest', 'C'): 73,      # C = clay loam
            ('forest', 'D'): 79,      # D = clay (low infiltration)
            
            ('agriculture', 'A'): 67,
            ('agriculture', 'B'): 78,
            ('agriculture', 'C'): 85,
            ('agriculture', 'D'): 89,
            
            ('urban_residential', 'A'): 77,
            ('urban_residential', 'B'): 85,
            ('urban_residential', 'C'): 90,
            ('urban_residential', 'D'): 92,
            
            ('urban_commercial', 'A'): 89,
            ('urban_commercial', 'B'): 92,
            ('urban_commercial', 'C'): 94,
            ('urban_commercial', 'D'): 95,
            
            ('water', 'A'): 100,
            ('water', 'B'): 100,
            ('water', 'C'): 100,
            ('water', 'D'): 100,
            
            ('barren', 'A'): 77,
            ('barren', 'B'): 86,
            ('barren', 'C'): 91,
            ('barren', 'D'): 94,
        }
    
    def calculate_runoff(self, rainfall_mm, curve_number, amc='II'):
        """
        Calculate direct runoff using SCS Curve Number method.
        
        Args:
            rainfall_mm: Total rainfall depth (mm)
            curve_number: SCS curve number (0-100)
            amc: Antecedent Moisture Condition ('I'=dry, 'II'=normal, 'III'=wet)
        
        Returns:
            runoff_mm: Direct runoff depth (mm)
        
        Formula:
            S = (25400 / CN) - 254        (maximum retention in mm)
            Ia = 0.2 * S                  (initial abstraction)
            Q = (P - Ia)² / (P - Ia + S)  (runoff depth)
            
            where P = rainfall, Q = runoff
        """
        # Adjust CN for antecedent moisture
        if amc == 'I':  # Dry conditions
            cn_adjusted = curve_number / (2.281 - 0.01281 * curve_number)
        elif amc == 'III':  # Wet conditions
            cn_adjusted = curve_number / (0.427 + 0.00573 * curve_number)
        else:  # Normal (II)
            cn_adjusted = curve_number
        
        # Calculate potential maximum retention
        S = (25400 / cn_adjusted) - 254
        
        # Initial abstraction (interception + infiltration before runoff starts)
        Ia = 0.2 * S
        
        # Calculate runoff (only if rainfall exceeds initial abstraction)
        if rainfall_mm <= Ia:
            return 0.0
        
        runoff_mm = ((rainfall_mm - Ia) ** 2) / (rainfall_mm - Ia + S)
        
        return runoff_mm
    
    def get_curve_number_raster(self, landuse_raster, soil_raster, output_path):
        """
        Create a raster of curve numbers from land use and soil type rasters.
        
        Args:
            landuse_raster: path to land use classification raster
            soil_raster: path to soil hydrologic group raster
            output_path: where to save CN raster
        
        Returns:
            path to curve number raster
        """
        with rasterio.open(landuse_raster) as lu_src:
            landuse = lu_src.read(1)
            profile = lu_src.profile
        
        with rasterio.open(soil_raster) as soil_src:
            soil = soil_src.read(1)
        
        # Create empty CN array
        cn = np.zeros_like(landuse, dtype=np.float32)
        
        # Map land use codes to names
        lu_mapping = {
            1: 'forest',
            2: 'agriculture',
            3: 'urban_residential',
            4: 'urban_commercial',
            5: 'water',
            6: 'barren'
        }
        
        # Map soil codes to groups
        soil_mapping = {
            1: 'A',
            2: 'B',
            3: 'C',
            4: 'D'
        }
        
        # Assign CN values
        for lu_code, lu_name in lu_mapping.items():
            for soil_code, soil_group in soil_mapping.items():
                mask = (landuse == lu_code) & (soil == soil_code)
                cn_value = self.curve_numbers.get((lu_name, soil_group), 75)
                cn[mask] = cn_value
        
        # Save
        profile.update(dtype=rasterio.float32, count=1)
        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(cn, 1)
        
        return output_path
    
    def calculate_watershed_runoff(self, rainfall_mm, cn_raster, watershed_shp):
        """
        Calculate average runoff for entire watershed.
        
        Args:
            rainfall_mm: Rainfall depth (mm)
            cn_raster: Path to curve number raster
            watershed_shp: Path to watershed boundary shapefile
        
        Returns:
            dict with runoff statistics
        """
        # Load watershed
        watershed = gpd.read_file(watershed_shp)
        
        # Calculate zonal statistics
        stats = zonal_stats(
            watershed,
            cn_raster,
            stats=['mean', 'median', 'std', 'min', 'max']
        )
        
        avg_cn = stats[0]['mean']
        
        # Calculate runoff
        runoff = self.calculate_runoff(rainfall_mm, avg_cn)
        
        return {
            'rainfall_mm': rainfall_mm,
            'avg_curve_number': avg_cn,
            'runoff_mm': runoff,
            'runoff_coefficient': runoff / rainfall_mm if rainfall_mm > 0 else 0,
            'infiltration_mm': rainfall_mm - runoff
        }
    
    def time_series_runoff(self, rainfall_timeseries, cn_raster, watershed_shp):
        """
        Calculate runoff for a time series of rainfall events.
        
        Args:
            rainfall_timeseries: DataFrame with columns ['datetime', 'rainfall_mm']
            cn_raster: Path to curve number raster
            watershed_shp: Path to watershed boundary shapefile
        
        Returns:
            DataFrame with runoff time series
        """
        results = []
        
        # Get average CN for watershed
        watershed = gpd.read_file(watershed_shp)
        stats = zonal_stats(watershed, cn_raster, stats=['mean'])
        avg_cn = stats[0]['mean']
        
        # Determine AMC based on previous 5 days rainfall
        for idx, row in rainfall_timeseries.iterrows():
            # Get previous 5 days
            if idx >= 5:
                prev_5day_rain = rainfall_timeseries.iloc[idx-5:idx]['rainfall_mm'].sum()
            else:
                prev_5day_rain = 0
            
            # Classify AMC
            if prev_5day_rain < 35:
                amc = 'I'   # Dry
            elif prev_5day_rain > 50:
                amc = 'III' # Wet
            else:
                amc = 'II'  # Normal
            
            # Calculate runoff
            rainfall = row['rainfall_mm']
            runoff = self.calculate_runoff(rainfall, avg_cn, amc=amc)
            
            results.append({
                'datetime': row['datetime'],
                'rainfall_mm': rainfall,
                'curve_number': avg_cn,
                'amc': amc,
                'runoff_mm': runoff,
                'infiltration_mm': rainfall - runoff
            })
        
        return pd.DataFrame(results)


class RainfallDataFetcher:
    """
    Downloads rainfall data from NASA GPM or CHIRPS.
    """
    
    def fetch_gpm_data(self, bounds, start_date, end_date, output_file):
        """
        Fetch NASA GPM rainfall data.
        
        Args:
            bounds: (west, south, east, north)
            start_date: datetime
            end_date: datetime
            output_file: where to save netCDF
        
        Note: Requires NASA Earthdata account and credentials.
        See: https://disc.gsfc.nasa.gov/data-access
        """
        # This is a simplified example
        # Real implementation requires NASA API credentials
        
        print("Fetching GPM data...")
        print("This requires NASA Earthdata credentials.")
        print("For full implementation, use the GES DISC API:")
        print("https://disc.gsfc.nasa.gov/data-access")
        
        # Placeholder - in real use, you'd call the NASA API here
        # using requests library with authentication
        
        return output_file
    
    def fetch_chirps_data(self, bounds, start_date, end_date, output_dir):
        """
        Fetch CHIRPS daily rainfall data.
        
        CHIRPS provides global daily rainfall at 0.05° resolution.
        Data available from 1981 to near-present.
        
        Download from: https://data.chc.ucsb.edu/products/CHIRPS-2.0/
        """
        print("Downloading CHIRPS data...")
        print("Visit: https://data.chc.ucsb.edu/products/CHIRPS-2.0/")
        print(f"Date range: {start_date} to {end_date}")
        print(f"Bounds: {bounds}")
        
        # CHIRPS data can be downloaded via FTP
        # For full automation, use wget or requests to download
        # the daily GeoTIFF files
        
        return output_dir
    
    def extract_watershed_rainfall(self, rainfall_raster, watershed_shp):
        """
        Extract average rainfall over watershed.
        
        Args:
            rainfall_raster: path to rainfall GeoTIFF or netCDF
            watershed_shp: path to watershed shapefile
        
        Returns:
            average rainfall in mm
        """
        watershed = gpd.read_file(watershed_shp)
        stats = zonal_stats(watershed, rainfall_raster, stats=['mean', 'sum'])
        
        return stats[0]['mean']
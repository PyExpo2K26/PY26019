# ═══════════════════════════════════════════════════════════════════════════
# INFRASTRUCTURE IMPACT ASSESSMENT
# ═══════════════════════════════════════════════════════════════════════════

"""
This module identifies which buildings, roads, and infrastructure
are affected by flooding at different water levels.

OUTPUTS:
- List of buildings in flood zone with depth
- Road segments that become impassable
- Critical infrastructure at risk (hospitals, schools, power stations)
- Population exposure estimates
- Damage cost estimates
"""

# FILE: utils/infrastructure_assessment.py

import os
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from rasterstats import zonal_stats, point_query
from shapely.geometry import Point, LineString, Polygon
import osmnx as ox

class InfrastructureAssessor:
    """
    Assess flood impact on buildings, roads, and infrastructure.
    """
    
    def __init__(self, location, bounds, workspace='hydro_data'):
        """
        Args:
            location: city name
            bounds: (west, south, east, north)
            workspace: directory for data
        """
        self.location = location
        self.bounds = bounds
        self.workspace = workspace
        
        self.location_name = location.split(',')[0].lower()
        self.output_dir = os.path.join(workspace, self.location_name, 'infrastructure')
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Infrastructure data (downloaded once)
        self.buildings = None
        self.roads = None
        self.pois = None  # Points of interest
    
    def download_infrastructure_data(self, progress_callback=None):
        """
        Download building footprints and road network from OpenStreetMap.
        
        Returns:
            dict with paths to downloaded shapefiles
        """
        if progress_callback:
            progress_callback("Downloading buildings from OpenStreetMap...")
        
        # Download buildings
        try:
            buildings = ox.features_from_bbox(
                north=self.bounds[3],
                south=self.bounds[1],
                east=self.bounds[2],
                west=self.bounds[0],
                tags={'building': True}
            )
            
            # Keep only polygons
            buildings = buildings[buildings.geometry.type == 'Polygon']
            
            # Save
            buildings_path = os.path.join(self.output_dir, 'buildings.shp')
            buildings.to_file(buildings_path)
            self.buildings = buildings
            
            print(f"Downloaded {len(buildings)} buildings")
        
        except Exception as e:
            print(f"Building download failed: {e}")
            buildings_path = None
        
        if progress_callback:
            progress_callback("Downloading road network...")
        
        # Download roads
        try:
            roads = ox.graph_to_gdfs(
                ox.graph_from_bbox(
                    north=self.bounds[3],
                    south=self.bounds[1],
                    east=self.bounds[2],
                    west=self.bounds[0],
                    network_type='drive'
                ),
                nodes=False,
                edges=True
            )
            
            # Save
            roads_path = os.path.join(self.output_dir, 'roads.shp')
            roads.to_file(roads_path)
            self.roads = roads
            
            print(f"Downloaded {len(roads)} road segments")
        
        except Exception as e:
            print(f"Road download failed: {e}")
            roads_path = None
        
        if progress_callback:
            progress_callback("Downloading critical infrastructure...")
        
        # Download critical facilities (hospitals, schools, fire stations, etc)
        try:
            pois = ox.features_from_bbox(
                north=self.bounds[3],
                south=self.bounds[1],
                east=self.bounds[2],
                west=self.bounds[0],
                tags={
                    'amenity': ['hospital', 'school', 'fire_station', 'police'],
                    'emergency': True
                }
            )
            
            pois_path = os.path.join(self.output_dir, 'critical_facilities.shp')
            pois.to_file(pois_path)
            self.pois = pois
            
            print(f"Downloaded {len(pois)} critical facilities")
        
        except Exception as e:
            print(f"POI download failed: {e}")
            pois_path = None
        
        return {
            'buildings': buildings_path,
            'roads': roads_path,
            'pois': pois_path
        }
    
    def assess_building_flood_risk(self, flood_depth_raster, output_path=None):
        """
        Identify buildings in flood zone and extract flood depth at each building.
        
        Args:
            flood_depth_raster: path to flood depth raster
            output_path: where to save results
        
        Returns:
            GeoDataFrame with buildings and flood depths
        """
        if self.buildings is None:
            raise ValueError("Buildings not loaded. Call download_infrastructure_data() first.")
        
        if output_path is None:
            rainfall = os.path.basename(flood_depth_raster).split('_')[2].replace('.tif', '')
            output_path = os.path.join(self.output_dir, f'flooded_buildings_{rainfall}.shp')
        
        print(f"Assessing {len(self.buildings)} buildings...")
        
        # Extract flood depth at each building centroid
        centroids = self.buildings.geometry.centroid
        
        depths = []
        for centroid in centroids:
            try:
                # Query raster at point
                with rasterio.open(flood_depth_raster) as src:
                    row, col = src.index(centroid.x, centroid.y)
                    depth = src.read(1)[row, col]
                    depths.append(depth)
            except:
                depths.append(0)
        
        # Add depth to buildings
        buildings_with_depth = self.buildings.copy()
        buildings_with_depth['flood_depth_m'] = depths
        
        # Classify damage
        buildings_with_depth['damage_category'] = pd.cut(
            buildings_with_depth['flood_depth_m'],
            bins=[-np.inf, 0, 0.5, 1.0, 2.0, np.inf],
            labels=['None', 'Minor', 'Moderate', 'Significant', 'Severe']
        )
        
        # Filter to flooded buildings only
        flooded_buildings = buildings_with_depth[buildings_with_depth['flood_depth_m'] > 0.1]
        
        # Save
        flooded_buildings.to_file(output_path)
        
        print(f"Found {len(flooded_buildings)} flooded buildings")
        print(f"  Minor damage:       {(flooded_buildings['damage_category'] == 'Minor').sum()}")
        print(f"  Moderate damage:    {(flooded_buildings['damage_category'] == 'Moderate').sum()}")
        print(f"  Significant damage: {(flooded_buildings['damage_category'] == 'Significant').sum()}")
        print(f"  Severe damage:      {(flooded_buildings['damage_category'] == 'Severe').sum()}")
        
        return flooded_buildings
    
    def assess_road_accessibility(self, flood_depth_raster, output_path=None):
        """
        Identify road segments that become impassable due to flooding.
        
        Thresholds:
        - > 0.3m: Dangerous for vehicles
        - > 0.6m: Impassable
        
        Args:
            flood_depth_raster: path to flood depth raster
            output_path: where to save results
        
        Returns:
            GeoDataFrame with road segments and flood status
        """
        if self.roads is None:
            raise ValueError("Roads not loaded. Call download_infrastructure_data() first.")
        
        if output_path is None:
            rainfall = os.path.basename(flood_depth_raster).split('_')[2].replace('.tif', '')
            output_path = os.path.join(self.output_dir, f'flooded_roads_{rainfall}.shp')
        
        print(f"Assessing {len(self.roads)} road segments...")
        
        # Sample flood depth along each road segment
        roads_with_depth = self.roads.copy()
        max_depths = []
        
        for geom in self.roads.geometry:
            # Sample points along line
            try:
                points = [geom.interpolate(i, normalized=True) for i in np.linspace(0, 1, 10)]
                
                depths = []
                with rasterio.open(flood_depth_raster) as src:
                    for pt in points:
                        row, col = src.index(pt.x, pt.y)
                        depth = src.read(1)[row, col]
                        depths.append(depth)
                
                max_depths.append(max(depths))
            except:
                max_depths.append(0)
        
        roads_with_depth['flood_depth_m'] = max_depths
        
        # Classify accessibility
        roads_with_depth['accessibility'] = 'Passable'
        roads_with_depth.loc[roads_with_depth['flood_depth_m'] > 0.3, 'accessibility'] = 'Dangerous'
        roads_with_depth.loc[roads_with_depth['flood_depth_m'] > 0.6, 'accessibility'] = 'Impassable'
        
        # Filter to affected roads
        affected_roads = roads_with_depth[roads_with_depth['flood_depth_m'] > 0.1]
        
        # Save
        affected_roads.to_file(output_path)
        
        print(f"Found {len(affected_roads)} affected road segments")
        print(f"  Dangerous:   {(affected_roads['accessibility'] == 'Dangerous').sum()}")
        print(f"  Impassable:  {(affected_roads['accessibility'] == 'Impassable').sum()}")
        
        return affected_roads
    
    def assess_critical_facilities(self, flood_depth_raster, output_path=None):
        """
        Check if critical facilities (hospitals, schools, etc) are flooded.
        
        Returns:
            DataFrame with affected facilities
        """
        if self.pois is None:
            raise ValueError("POIs not loaded. Call download_infrastructure_data() first.")
        
        if output_path is None:
            rainfall = os.path.basename(flood_depth_raster).split('_')[2].replace('.tif', '')
            output_path = os.path.join(self.output_dir, f'affected_facilities_{rainfall}.csv')
        
        print(f"Assessing {len(self.pois)} critical facilities...")
        
        pois_with_depth = self.pois.copy()
        depths = []
        
        for geom in self.pois.geometry:
            try:
                centroid = geom.centroid if geom.geom_type == 'Polygon' else geom
                
                with rasterio.open(flood_depth_raster) as src:
                    row, col = src.index(centroid.x, centroid.y)
                    depth = src.read(1)[row, col]
                    depths.append(depth)
            except:
                depths.append(0)
        
        pois_with_depth['flood_depth_m'] = depths
        
        # Filter to flooded facilities
        flooded_facilities = pois_with_depth[pois_with_depth['flood_depth_m'] > 0.1]
        
        # Save
        flooded_facilities[['name', 'amenity', 'flood_depth_m']].to_csv(output_path, index=False)
        
        print(f"⚠️  {len(flooded_facilities)} critical facilities affected!")
        
        if len(flooded_facilities) > 0:
            print("\nAffected facilities:")
            for idx, row in flooded_facilities.iterrows():
                name = row.get('name', 'Unknown')
                facility_type = row.get('amenity', 'Unknown')
                depth = row['flood_depth_m']
                print(f"  • {name} ({facility_type}): {depth:.2f}m")
        
        return flooded_facilities
    
    def generate_impact_report(self, flood_depth_raster):
        """
        Generate complete infrastructure impact report.
        
        Returns:
            dict with all assessment results
        """
        print(f"\n{'='*70}")
        print(f"INFRASTRUCTURE IMPACT ASSESSMENT")
        print(f"Location: {self.location}")
        print(f"Scenario: {os.path.basename(flood_depth_raster)}")
        print(f"{'='*70}\n")
        
        # Run all assessments
        buildings = self.assess_building_flood_risk(flood_depth_raster)
        roads = self.assess_road_accessibility(flood_depth_raster)
        facilities = self.assess_critical_facilities(flood_depth_raster)
        
        # Compile report
        report = {
            'location': self.location,
            'scenario': os.path.basename(flood_depth_raster),
            'timestamp': pd.Timestamp.now().isoformat(),
            'buildings': {
                'total_flooded': len(buildings),
                'by_damage': buildings['damage_category'].value_counts().to_dict(),
                'max_depth': buildings['flood_depth_m'].max(),
                'avg_depth': buildings['flood_depth_m'].mean()
            },
            'roads': {
                'total_affected': len(roads),
                'by_accessibility': roads['accessibility'].value_counts().to_dict(),
                'max_depth': roads['flood_depth_m'].max()
            },
            'facilities': {
                'total_affected': len(facilities),
                'list': facilities[['name', 'amenity', 'flood_depth_m']].to_dict('records')
            }
        }
        
        # Print summary
        print(f"\n{'='*70}")
        print("IMPACT SUMMARY")
        print(f"{'='*70}")
        print(f"\nBuildings:")
        print(f"  Total flooded: {report['buildings']['total_flooded']}")
        for damage, count in report['buildings']['by_damage'].items():
            print(f"    {damage}: {count}")
        
        print(f"\nRoads:")
        print(f"  Total affected: {report['roads']['total_affected']}")
        for status, count in report['roads']['by_accessibility'].items():
            print(f"    {status}: {count}")
        
        print(f"\nCritical Facilities:")
        print(f"  Total affected: {report['facilities']['total_affected']}")
        
        print(f"\n{'='*70}\n")
        
        return report


# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════

"""
# Initialize assessor
assessor = InfrastructureAssessor(
    location='Mumbai, Maharashtra',
    bounds=(72.7, 18.8, 73.1, 19.3)
)

# Download infrastructure data (once)
files = assessor.download_infrastructure_data()

# Run assessment for a flood scenario
report = assessor.generate_impact_report(
    flood_depth_raster='hydro_data/mumbai/flood_depth_200mm.tif'
)

# Access specific results
print(f"Buildings flooded: {report['buildings']['total_flooded']}")
print(f"Roads impassable: {report['roads']['by_accessibility'].get('Impassable', 0)}")
print(f"Critical facilities affected: {report['facilities']['total_affected']}")
"""

# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO PLANNING MODULE - FLOOD HAZARD ZONE MAPPING
# ═══════════════════════════════════════════════════════════════════════════

"""
This module runs multiple rainfall scenarios to create flood hazard maps.

OUTPUT: Hazard zones showing which areas flood at different rainfall levels
- 50mm: Minor flooding (Low hazard)
- 100mm: Moderate flooding (Medium hazard)
- 150mm: Significant flooding (High hazard)
- 200mm+: Extreme flooding (Very High hazard)
"""

# FILE: utils/scenario_planner.py

import os
import numpy as np
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt

# ── FIX: robust import that works whether called from pages/ or utils/ ───────
try:
    from utils.combined_predictor import CombinedFloodPredictor
except ImportError:
    from combined_predictor import CombinedFloodPredictor
# ─────────────────────────────────────────────────────────────────────────────

# Optional heavy dependencies — only imported when actually needed
def _try_import_geo():
    try:
        import geopandas as gpd
        import rasterio
        from rasterio.merge import merge
        return True
    except ImportError:
        return False

def _try_import_folium():
    try:
        import folium
        from folium import plugins
        return True
    except ImportError:
        return False


class ScenarioPlanner:
    """
    Runs multiple rainfall scenarios to create flood hazard maps.
    """

    def __init__(self, location, workspace='hydro_data'):
        self.location  = location
        self.workspace = workspace
        # ── FIX: CombinedFloodPredictor is instantiated HERE (inside __init__),
        #         NOT at module level — that was the root cause of the NameError.
        self.predictor = CombinedFloodPredictor(workspace=workspace)

        # Scenario definitions
        self.standard_scenarios = {
            '2-year':   50,
            '5-year':   75,
            '10-year':  100,
            '25-year':  150,
            '50-year':  200,
            '100-year': 250,
            '200-year': 300,
        }

        self.results    = []
        self.hazard_map = None

    # ──────────────────────────────────────────────────────────────────────
    def run_all_scenarios(self, water_level=8.0, progress_callback=None):
        """
        Run all standard scenarios.

        Args:
            water_level       : base water level for all scenarios
            progress_callback : function(message) to report progress

        Returns:
            DataFrame with all scenario results
        """
        if progress_callback:
            progress_callback(f"Running {len(self.standard_scenarios)} scenarios...")

        self.results = []

        for i, (period, rainfall) in enumerate(self.standard_scenarios.items(), 1):
            if progress_callback:
                progress_callback(f"[{i}/{len(self.standard_scenarios)}] {period} event ({rainfall}mm)")

            result = self.predictor.predict(
                location    = self.location,
                rainfall    = rainfall,
                water_level = water_level,
                force_hydro = True,
                return_maps = False,
            )

            self.results.append({
                'return_period':       period,
                'rainfall_mm':         rainfall,
                'ml_probability':      result['ml_prediction']['probability'],
                'ml_risk_level':       result['ml_prediction']['risk_level'],
                'runoff_mm':           result['hydro_prediction'].get('runoff_mm', 0),
                'water_level_rise_m':  result['hydro_prediction'].get('water_level_rise_m', 0),
                'flooded_area_pct':    result['hydro_prediction'].get('flooded_area_pct', 0),
                'max_depth_m':         result['hydro_prediction'].get('max_depth_m', 0),
                'avg_depth_m':         result['hydro_prediction'].get('avg_depth_m', 0),
                'combined_risk':       result['combined_risk_level'],
                'flood_depth_raster':  result['hydro_prediction'].get('flood_depth_raster'),
                'severity_raster':     result['hydro_prediction'].get('severity_raster'),
            })

        results_df = pd.DataFrame(self.results)

        if progress_callback:
            progress_callback("All scenarios complete!")

        return results_df

    # ──────────────────────────────────────────────────────────────────────
    def create_hazard_map(self, output_path=None):
        """
        Combine all scenarios into a single flood hazard map.
        Requires rasterio — skipped gracefully if not installed.
        """
        if not self.results:
            raise ValueError("No scenarios run yet. Call run_all_scenarios() first.")

        if not _try_import_geo():
            print("rasterio not installed — skipping raster hazard map generation.")
            return None

        import rasterio

        if output_path is None:
            location_name = self.location.split(',')[0].lower().replace(' ', '_')
            output_path   = os.path.join(self.workspace, location_name, 'flood_hazard_map.tif')

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        print("Creating composite hazard map...")

        first_result = self.results[0]
        if first_result['flood_depth_raster'] is None:
            print("No raster data available (return_maps=False). Skipping hazard map.")
            return None

        with rasterio.open(first_result['flood_depth_raster']) as src:
            profile = src.profile
            shape   = src.shape

        hazard = np.zeros(shape, dtype=np.float32)

        for result in self.results:
            rainfall = result['rainfall_mm']
            if result['flood_depth_raster'] is None:
                continue
            with rasterio.open(result['flood_depth_raster']) as src:
                depth = src.read(1)
            flooded      = depth > 0.1
            needs_update = flooded & (hazard == 0)
            hazard[needs_update] = rainfall

        profile.update(dtype=rasterio.float32)
        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(hazard, 1)

        self.hazard_map = output_path
        print(f"Hazard map saved: {output_path}")
        return output_path

    # ──────────────────────────────────────────────────────────────────────
    def classify_hazard_zones(self, hazard_map_path=None, output_path=None):
        """Classify hazard map into discrete zones (requires rasterio)."""
        if not _try_import_geo():
            print("rasterio not installed — skipping zone classification.")
            return None

        import rasterio

        if hazard_map_path is None:
            hazard_map_path = self.hazard_map
        if hazard_map_path is None or not os.path.exists(hazard_map_path):
            print("No hazard map found to classify.")
            return None

        if output_path is None:
            output_path = hazard_map_path.replace('.tif', '_zones.tif')

        print("Classifying hazard zones...")

        with rasterio.open(hazard_map_path) as src:
            hazard  = src.read(1)
            profile = src.profile

        zones = np.zeros_like(hazard, dtype=np.uint8)
        zones[(hazard > 0)   & (hazard <= 75)]  = 4   # Very High
        zones[(hazard > 75)  & (hazard <= 125)] = 3   # High
        zones[(hazard > 125) & (hazard <= 175)] = 2   # Medium
        zones[hazard > 175]                     = 1   # Low

        profile.update(dtype=rasterio.uint8)
        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(zones, 1)

        print(f"Hazard zones saved: {output_path}")
        return output_path

    # ──────────────────────────────────────────────────────────────────────
    def create_summary_chart(self, results_df, output_path=None):
        """Create 2×2 visualization of scenario results."""
        if output_path is None:
            location_name = self.location.split(',')[0].lower().replace(' ', '_')
            output_path   = os.path.join(self.workspace, location_name, 'scenario_summary.png')

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # 1. Flooded area vs rainfall
        axes[0, 0].plot(results_df['rainfall_mm'], results_df['flooded_area_pct'],
                        marker='o', linewidth=2, markersize=8, color='#E53935')
        axes[0, 0].set_xlabel('Rainfall (mm)', fontsize=12)
        axes[0, 0].set_ylabel('Flooded Area (%)', fontsize=12)
        axes[0, 0].set_title('Flooded Area vs Rainfall', fontsize=14, fontweight='bold')
        axes[0, 0].grid(True, alpha=0.3)

        # 2. Max depth vs rainfall
        axes[0, 1].plot(results_df['rainfall_mm'], results_df['max_depth_m'],
                        marker='s', linewidth=2, markersize=8, color='#1E88E5')
        axes[0, 1].set_xlabel('Rainfall (mm)', fontsize=12)
        axes[0, 1].set_ylabel('Max Flood Depth (m)', fontsize=12)
        axes[0, 1].set_title('Maximum Flood Depth vs Rainfall', fontsize=14, fontweight='bold')
        axes[0, 1].grid(True, alpha=0.3)

        # 3. Runoff coefficient
        results_df = results_df.copy()
        results_df['runoff_coeff'] = results_df['runoff_mm'] / results_df['rainfall_mm']
        axes[1, 0].bar(results_df['return_period'], results_df['runoff_coeff'],
                       color='#43A047', alpha=0.7)
        axes[1, 0].set_xlabel('Return Period', fontsize=12)
        axes[1, 0].set_ylabel('Runoff Coefficient', fontsize=12)
        axes[1, 0].set_title('Runoff Efficiency by Event', fontsize=14, fontweight='bold')
        axes[1, 0].tick_params(axis='x', rotation=45)
        axes[1, 0].grid(True, alpha=0.3, axis='y')

        # 4. Risk level pie
        risk_counts  = results_df['combined_risk'].value_counts()
        colors_map   = {'Low': '#4CAF50', 'Medium': '#FF9800',
                        'High': '#F44336', 'Very High': '#B71C1C'}
        colors       = [colors_map.get(r, '#999999') for r in risk_counts.index]
        axes[1, 1].pie(risk_counts.values, labels=risk_counts.index,
                       autopct='%1.0f%%', colors=colors, startangle=90)
        axes[1, 1].set_title('Risk Level Distribution', fontsize=14, fontweight='bold')

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        print(f"Summary chart saved: {output_path}")
        return output_path

    # ──────────────────────────────────────────────────────────────────────
    def export_results(self, results_df, output_format='csv'):
        """Export scenario results to csv / excel / json."""
        location_name = self.location.split(',')[0].lower().replace(' ', '_')
        base_dir      = os.path.join(self.workspace, location_name)
        os.makedirs(base_dir, exist_ok=True)

        fmt_map = {
            'csv':   (os.path.join(base_dir, 'scenario_results.csv'),
                      lambda p: results_df.to_csv(p, index=False)),
            'excel': (os.path.join(base_dir, 'scenario_results.xlsx'),
                      lambda p: results_df.to_excel(p, index=False, sheet_name='Scenarios')),
            'json':  (os.path.join(base_dir, 'scenario_results.json'),
                      lambda p: results_df.to_json(p, orient='records', indent=2)),
        }

        if output_format not in fmt_map:
            raise ValueError(f"Unknown format '{output_format}'. Choose csv, excel, or json.")

        output_path, save_fn = fmt_map[output_format]
        save_fn(output_path)
        print(f"Results exported: {output_path}")
        return output_path

    # ──────────────────────────────────────────────────────────────────────
    def generate_report(self, results_df):
        """Generate a text report summarising all scenarios."""
        lines = []
        lines.append("=" * 70)
        lines.append("FLOOD SCENARIO ANALYSIS REPORT")
        lines.append(f"Location:  {self.location}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 70)
        lines.append("")
        lines.append("SCENARIO SUMMARY")
        lines.append("-" * 70)

        for _, row in results_df.iterrows():
            lines.append(f"\n{row['return_period'].upper()} EVENT ({row['rainfall_mm']}mm):")
            lines.append(f"  • ML Probability:   {row['ml_probability']:.1%}")
            lines.append(f"  • Runoff Generated: {row['runoff_mm']:.1f} mm")
            lines.append(f"  • Water Level Rise: {row['water_level_rise_m']:.2f} m")
            lines.append(f"  • Flooded Area:     {row['flooded_area_pct']:.1f}%")
            lines.append(f"  • Maximum Depth:    {row['max_depth_m']:.2f} m")
            lines.append(f"  • Combined Risk:    {row['combined_risk']}")

        lines.append("\n" + "=" * 70)
        lines.append("KEY FINDINGS")
        lines.append("=" * 70)

        minor   = results_df[results_df['return_period'] == '2-year'].iloc[0]
        extreme = results_df[results_df['return_period'] == '100-year'].iloc[0]

        lines.append(f"\n• 2-year event floods   {minor['flooded_area_pct']:.1f}% of area")
        lines.append(f"• 100-year event floods {extreme['flooded_area_pct']:.1f}% of area")
        lines.append(f"• Maximum depth across all scenarios: {results_df['max_depth_m'].max():.2f} m")
        lines.append(f"• Avg runoff coefficient: "
                     f"{(results_df['runoff_mm'] / results_df['rainfall_mm']).mean():.2f}")

        high_risk = results_df[results_df['combined_risk'].isin(['High', 'Very High'])]
        lines.append(f"• {len(high_risk)}/{len(results_df)} scenarios trigger High/Very High risk")

        lines.append("\n" + "=" * 70)
        return "\n".join(lines)

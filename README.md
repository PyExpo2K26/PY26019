Abstract
A Python and Machine Learning-based system that predicts flood risks using historical rainfall and river water-level data. When predicted risk exceeds a safe threshold, alerts are generated and safe evacuation routes are suggested via map integration.

Objectives

Analyze historical rainfall and river-level data
Predict flood probability using ML models
Provide early flood warnings and alerts
Suggest safe evacuation routes using maps
Reduce loss of life and property during floods


Software Requirements
ToolPurposePython 3.xCore languageStreamlitWeb UINumPy / PandasData processingScikit-learnML modelsMatplotlibVisualizationFoliumMap integration

Hardware Requirements

Processor: Intel i3 or above
RAM: Minimum 4 GB
Storage: 10 GB free space
OS: Windows / Linux


Methodology

Collect historical rainfall and river-level data
Preprocess data (cleaning, normalization)
Apply hydrological and hydraulic modeling
Train ML model for flood probability prediction
Generate alert when risk exceeds threshold
Visualize safe routes using map integration


Modules

Data Collection — Gathers historical datasets
Preprocessing — Cleans and normalizes data
Hydrology Module — Computes runoff using SCS-CN method
Hydraulic Module — Estimates flow using Manning's equation
Prediction Module — Predicts flood probability via ML
Alert Module — Triggers warning when risk exceeds threshold
Map Module — Displays safe routes and affected areas


Model Training
1. Hydrological Model
Hydrology models the movement of water through the watershed — from rainfall to runoff. It estimates how much rainfall becomes surface runoff based on soil type, land use, and moisture conditions.
Method: SCS-CN (Soil Conservation Service Curve Number)
The potential maximum retention is calculated as:
S = (25400 / CN) - 254
The initial abstraction (water lost before runoff begins) is:
Ia = 0.2 × S
The actual surface runoff is then estimated as:
Q = (P - Ia)² / (P - Ia + S)
Where:

P = Rainfall (mm)
CN = Curve Number (based on soil and land use, ranges 0–100)
S = Potential maximum retention (mm)
Ia = Initial abstraction (mm)
Q = Surface runoff (mm)

Key Features Extracted:

Antecedent soil moisture
Catchment area (km²)
Land use type
Terrain slope (%)
Time of concentration and peak discharge


2. Hydraulic Model
Hydraulics models how water flows through river channels and floodplains — including flow velocity, water depth, and total discharge.
Method: Manning's Equation
Flow velocity is calculated as:
V = (1/n) × R^(2/3) × S^(1/2)
Total discharge through the channel cross-section is:
Q = A × V
Where:

V = Flow velocity (m/s)
n = Manning's roughness coefficient (depends on channel material)
R = Hydraulic radius (m) = Cross-sectional area / Wetted perimeter
S = Channel bed slope (m/m)
Q = Discharge (m³/s)
A = Cross-sectional area of flow (m²)

Key Outputs:

Stage-discharge relationship (water level mapped to flow rate)
Flood inundation extent based on discharge values
Flow velocity and depth across the floodplain


3. Integrated ML Pipeline
The outputs from both the hydrological and hydraulic models are combined with raw field observations to form the complete feature set for machine learning.
Feature Set Used for Training:
FeatureSourceRainfall (mm)Field observationRunoff depth (mm)SCS-CN outputRiver water level (m)Field observationDischarge (m³/s)Manning's equation outputSoil moistureField observationCatchment area (km²)Watershed analysisSlope (%)Terrain data
Algorithm: Random Forest Classifier

Trained on historical flood and non-flood events
Outputs flood probability between 0 and 1
Alert is triggered when probability exceeds 0.70


Model Summary
ComponentMethodOutputHydrologySCS-CNRunoff depth (mm)HydraulicsManning's EquationDischarge and velocityPredictionRandom ForestFlood probability (0–1)AlertThreshold 0.70Warning triggered

Advantages

Physics-informed predictions combining hydrology, hydraulics, and ML
Early flood warning with configurable thresholds
User-friendly Streamlit interface
Visual safe-route suggestions via Folium maps


Applications

Disaster management systems
Flood-prone region monitoring
Government and municipal planning
Emergency response teams


Future Enhancements

Real-time weather API integration
SMS and mobile push notifications
Deep learning models using LSTM for time-series forecasting
Cloud-based deployment on AWS or GCP
Integration with HEC-RAS for advanced hydraulic simulation


Conclusion
The Flood Prediction and Alert System combines hydrological modeling using SCS-CN, hydraulic analysis using Manning's equation, and machine learning using Random Forest to deliver accurate and physics-grounded flood predictions. Timely alerts and map-based evacuation routes help minimize flood-related damage and improve disaster preparedness.
https://drive.google.com/file/d/1CL89nzGARlpyn5_FjgGke7z18KbGJv6Z/view?usp=sharing - demo video

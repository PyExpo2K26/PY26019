                            FLOOD PREDICTION AND ALERT SYSTEM


Abstract:

A Python and Machine Learning-based system that predicts flood risks using historical rainfall and river water-level data. When predicted risk exceeds a safe threshold, alerts are generated and safe evacuation routes are suggested via map integration.And now we included the chatbox in which if we ask any question related to this flood , it gives the answer related to this.

Objectives:

Analyze historical rainfall and river-level data
Predict flood probability using ML models
Provide early flood warnings and alerts
Suggest safe evacuation routes using maps
Reduce loss of life and property during floods


Software Requirements:

ToolPurpose: 

Python 3.x      Core language
Flask           Backend framework
Streamlit       Web UI
NumPy/Pandas    Data processing
Scikit-learn    ML models
Matplotlib      Visualization
Folium          Map integration
MySQL           Database

Hardware Requirements:

Processor: Intel i3 or above
RAM: Minimum 4 GB
Storage: 10 GB free space
OS: Windows / Linux


Methodology:

Collect historical rainfall and river-level data
Preprocess data (cleaning, normalization)
Apply hydrological and hydraulic modeling
Train ML model for flood probability prediction
Generate alert when risk exceeds threshold
Visualize safe routes using map integration


Modules:

Data Collection — Gathers historical datasets
Preprocessing — Cleans and normalizes data
Hydrology Module — Computes runoff using SCS-CN method
Hydraulic Module — Estimates flow using Manning's equation
Prediction Module — Predicts flood probability via Logistic Regression
Alert Module — Triggers warning when risk exceeds threshold
Map Module — Displays safe routes and affected areas


Model Training:

1. Hydrological Model — SCS-CN Method
Hydrology models the movement of water through the watershed from rainfall to runoff. It estimates how much rainfall becomes surface runoff based on soil type, land use, and moisture conditions.
Maximum Soil Retention
S = (25400 / CN) — 254
Initial Abstraction
Ia = 0.2 × S
Surface Runoff Depth
Q = (P — Ia)² / (P — Ia + S)
SymbolMeaningPRainfall (mm)CNCurve Number (0 to 100)SPotential maximum retention (mm)IaInitial abstraction (mm)QSurface runoff depth (mm)

Key Features Extracted:

Antecedent soil moisture
Catchment area (km²)
Land use type
Terrain slope (%)
Time of concentration and peak discharge


2. Hydraulic Model — Manning's Equation
   
Hydraulics models how water flows through river channels and floodplains including flow velocity, water depth, and total discharge.
Hydraulic Radius
R = A / P
Flow Velocity
V = (1 / n) × R^(2/3) × S^(1/2)
River Discharge
Q = A × V
Froude Number
Fr = V / √(g × D)

SymbolMeaning:

V               Flow velocity (m/s)
n               Manning's roughness coefficient
R               Hydraulic radius (m)
S               Channel bed slope (m/m)
Q               Discharge (m³/s)
A               Cross-sectional area (m²)
Fr              Froude Number (dimensionless)
Key Outputs:

Stage-discharge relationship
Flood inundation extent
Flow velocity and depth across floodplain


3. Machine Learning Model — Logistic Regression

Logistic Regression is used for binary flood classification — flood (1) or no flood (0). It outputs a flood probability between 0 and 1.
Linear Combination
z = b0 + b1x1 + b2x2 + b3x3 + ... + bnxn
Sigmoid Function — Flood Probability
P = 1 / (1 + e^(-z))
Alert Decision
If P ≥ 0.70 → Flood Alert Triggered
If P < 0.70 → No Alert
Log Loss — Cost Function
L = —(1/n) × Σ [ y × log(P) + (1—y) × log(1—P) ]
Gradient Descent — Weight Update
bj = bj — α × (∂L / ∂bj)

Feature Set Used for Training:

FeatureSource:

Rainfall (mm)           Field observation
Runoff depth(mm)        SCS-CN output
River water level(m)    Field observation
Discharge (m³/s)        Manning's output
Velocity (m/s)          Manning's output
Soil moisture           Field observation
Catchment area (km²)    Watershed data
Slope (%)               Terrain data

5. Model Evaluation
 
Accuracy = (TP + TN) / (TP + TN + FP + FN)
Precision = TP / (TP + FP)
Recall = TP / (TP + FN)
F1 Score = 2 × (Precision × Recall) / (Precision + Recall)
Recall is the most critical metric because missing a real flood is more dangerous than a false alarm.

Table Relationships:

Weather Station → Rainfall Data (station_id)
Weather Station → River Level Data (station_id)
Weather Station → Flood Prediction (station_id)
Weather Station → Alert (station_id)
Weather Station → Safe Route (station_id)
Watershed → Flood Prediction (watershed_id)
Flood Prediction → Alert (prediction_id)

Chatbot Module:

Overview:

An AI-powered chatbot is integrated into the Flood Prediction and Alert System to help users interact with the system using simple natural language. Instead of reading complex prediction reports, users can simply type a question and get an instant clear answer.


How It Works:

User types a flood-related question in the chat window
Chatbot receives the query and fetches relevant data from MySQL database
AI model processes the query and generates a human-readable response
Response is displayed instantly in the Streamlit chat interface


Key Features:

Answers flood risk queries in real time
Explains prediction results in simple language
Guides users during flood emergencies
Suggests safe evacuation routes on request
Fetches live data from rainfall, river level, and prediction tables
Available 24/7 without any human operator

Technology:

AI language model connected via API
Integrated with MySQL for live data fetching
Embedded as interactive chat window in Streamlit UI


System Architecture:

Layer 1 — Data Collection
Rainfall, river level, and soil data collected and stored in MySQL
Layer 2 — Hydrological Model
SCS-CN computes surface runoff depth from rainfall and CN value
Layer 3 — Hydraulic Model
Manning's equation computes river discharge and flow velocity from runoff
Layer 4 — ML Prediction
Logistic Regression predicts flood probability from all combined features
Layer 5 — Alert and Routing
Alert generated if probability exceeds 0.70 and safe evacuation routes displayed on Folium map

Advantages:

Physics-informed predictions combining hydrology, hydraulics, and ML
Four-level risk classification for graduated emergency response
Early flood warning with configurable thresholds
Complete end-to-end system from raw data to evacuation routing
User-friendly interface accessible to non-technical users
Zero licensing cost — fully open source
Self-improving system that learns from historical flood events


Applications:

Disaster management systems
Flood-prone region monitoring
Government and municipal planning
Emergency response teams


Future Enhancements:

Real-time weather API integration
SMS and mobile push notifications
Deep learning models using LSTM for time-series forecasting
Cloud-based deployment on AWS or GCP
Integration with HEC-RAS for advanced hydraulic simulation


Conclusion:

The Flood Prediction and Alert System combines hydrological modeling using SCS-CN, hydraulic analysis using Manning's equation, and machine learning using Logistic Regression to deliver accurate and physics-grounded flood predictions. Timely alerts and map-based evacuation routes help minimize flood-related damage and improve disaster preparedness.And the chatbot is included which is very usefull to find the answer for the question related to the flood.



https://drive.google.com/file/d/1CL89nzGARlpyn5_FjgGke7z18KbGJv6Z/view?usp=sharing  -- demo video link

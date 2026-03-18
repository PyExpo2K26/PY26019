import requests
from math import radians, sin, cos, sqrt, atan2

class LocationTracker:
    """Location tracking with automatic flood risk detection"""
    
    def __init__(self):
        self.current_location = None
        self.flood_prone_regions = self._load_flood_prone_database()
    
    def _load_flood_prone_database(self):
        """Database of known flood-prone regions with risk factors"""
        return {
            # India
            'Mumbai': {'risk_factor': 1.3, 'coords': (19.0760, 72.8777), 'country': 'India'},
            'Kolkata': {'risk_factor': 1.2, 'coords': (22.5726, 88.3639), 'country': 'India'},
            'Chennai': {'risk_factor': 1.2, 'coords': (13.0827, 80.2707), 'country': 'India'},
            'Assam': {'risk_factor': 1.5, 'coords': (26.2006, 92.9376), 'country': 'India'},
            'Kerala': {'risk_factor': 1.4, 'coords': (10.8505, 76.2711), 'country': 'India'},
            'Bihar': {'risk_factor': 1.4, 'coords': (25.0961, 85.3131), 'country': 'India'},
            'Uttarakhand': {'risk_factor': 1.3, 'coords': (30.0668, 79.0193), 'country': 'India'},
            'Andhra Pradesh': {'risk_factor': 1.2, 'coords': (15.9129, 79.7400), 'country': 'India'},
            'Hyderabad': {'risk_factor': 1.1, 'coords': (17.3850, 78.4867), 'country': 'India'},
            'Bangalore': {'risk_factor': 1.0, 'coords': (12.9716, 77.5946), 'country': 'India'},
            
            # Other countries
            'Bangladesh': {'risk_factor': 1.6, 'coords': (23.6850, 90.3563), 'country': 'Bangladesh'},
            'Jakarta': {'risk_factor': 1.3, 'coords': (-6.2088, 106.8456), 'country': 'Indonesia'},
            'Bangkok': {'risk_factor': 1.2, 'coords': (13.7563, 100.5018), 'country': 'Thailand'},
            'New Orleans': {'risk_factor': 1.4, 'coords': (29.9511, -90.0715), 'country': 'USA'},
            'Venice': {'risk_factor': 1.5, 'coords': (45.4408, 12.3155), 'country': 'Italy'},
            'Amsterdam': {'risk_factor': 1.3, 'coords': (52.3676, 4.9041), 'country': 'Netherlands'},
        }
    
    def get_location_by_ip(self):
        """Get user's current location using IP address"""
        try:
            url = "http://ip-api.com/json/"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                if data['status'] == 'success':
                    location = {
                        'method': 'IP Geolocation',
                        'latitude': data.get('lat'),
                        'longitude': data.get('lon'),
                        'city': data.get('city'),
                        'region': data.get('regionName'),
                        'country': data.get('country'),
                        'country_code': data.get('countryCode'),
                        'zip_code': data.get('zip'),
                        'timezone': data.get('timezone'),
                        'isp': data.get('isp'),
                        'ip': data.get('query'),
                        'accuracy': 'City-level',
                        'success': True
                    }
                    
                    self.current_location = location
                    location['flood_risk_assessment'] = self.assess_flood_risk(
                        location['latitude'], 
                        location['longitude'],
                        location['city']
                    )
                    
                    return location
            
            return {'success': False, 'error': 'Could not detect location'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def forward_geocode(self, address_string):
        """Convert address/city name to coordinates"""
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': address_string,
                'format': 'json',
                'limit': 1
            }
            headers = {
                'User-Agent': 'FloodPredictionApp/1.0'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                if len(data) > 0:
                    result = data[0]
                    location = {
                        'latitude': float(result.get('lat')),
                        'longitude': float(result.get('lon')),
                        'display_name': result.get('display_name'),
                        'type': result.get('type'),
                        'importance': result.get('importance'),
                        'success': True
                    }
                    
                    # Get detailed address
                    address_details = self.reverse_geocode(location['latitude'], location['longitude'])
                    if address_details:
                        location['city'] = address_details.get('city', 'Unknown')
                        location['state'] = address_details.get('state', 'Unknown')
                        location['country'] = address_details.get('country', 'Unknown')
                    
                    # Assess flood risk
                    location['flood_risk_assessment'] = self.assess_flood_risk(
                        location['latitude'], 
                        location['longitude'],
                        location.get('city', address_string)
                    )
                    
                    return location
            
            return {'success': False, 'error': 'Location not found'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def reverse_geocode(self, latitude, longitude):
        """Convert coordinates to address"""
        try:
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                'lat': latitude,
                'lon': longitude,
                'format': 'json'
            }
            headers = {
                'User-Agent': 'FloodPredictionApp/1.0'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                address = data.get('address', {})
                
                return {
                    'full_address': data.get('display_name'),
                    'city': address.get('city', address.get('town', address.get('village'))),
                    'state': address.get('state'),
                    'postcode': address.get('postcode'),
                    'country': address.get('country'),
                    'country_code': address.get('country_code')
                }
            
            return None
            
        except Exception as e:
            return None
    
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two coordinates (in kilometers)"""
        R = 6371.0  # Earth radius in kilometers
        
        lat1_rad = radians(lat1)
        lon1_rad = radians(lon1)
        lat2_rad = radians(lat2)
        lon2_rad = radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        return distance
    
    def find_nearest_flood_prone_area(self, user_lat, user_lon):
        """Find nearest known flood-prone area from database"""
        nearest = None
        min_distance = float('inf')
        
        for area_name, area_data in self.flood_prone_regions.items():
            area_lat, area_lon = area_data['coords']
            distance = self.calculate_distance(user_lat, user_lon, area_lat, area_lon)
            
            if distance < min_distance:
                min_distance = distance
                nearest = {
                    'name': area_name,
                    'distance_km': round(distance, 2),
                    'risk_factor': area_data['risk_factor'],
                    'country': area_data['country']
                }
        
        return nearest
    
    def assess_flood_risk(self, latitude, longitude, city_name=None):
        """Assess flood risk for any location"""
        nearest_area = self.find_nearest_flood_prone_area(latitude, longitude)
        
        base_risk = 1.0
        risk_level = "Unknown"
        risk_color = "gray"
        
        if nearest_area:
            distance = nearest_area['distance_km']
            
            if distance < 50:
                base_risk = nearest_area['risk_factor']
                risk_level = "High"
                risk_color = "red"
            elif distance < 150:
                base_risk = 1.0 + (nearest_area['risk_factor'] - 1.0) * 0.5
                risk_level = "Medium"
                risk_color = "orange"
            elif distance < 300:
                base_risk = 1.0 + (nearest_area['risk_factor'] - 1.0) * 0.2
                risk_level = "Low to Medium"
                risk_color = "yellow"
            else:
                base_risk = 1.0
                risk_level = "Low"
                risk_color = "green"
        
        # Check if city is in known database
        if city_name:
            for area_name, area_data in self.flood_prone_regions.items():
                if city_name.lower() in area_name.lower() or area_name.lower() in city_name.lower():
                    base_risk = area_data['risk_factor']
                    risk_level = "High" if base_risk > 1.3 else "Medium" if base_risk > 1.1 else "Low"
                    risk_color = "red" if base_risk > 1.3 else "orange" if base_risk > 1.1 else "yellow"
                    break
        
        return {
            'risk_factor': round(base_risk, 2),
            'risk_level': risk_level,
            'risk_color': risk_color,
            'nearest_flood_area': nearest_area,
            'assessment_method': 'Proximity-based + Database lookup'
        }
    
    def get_comprehensive_location_data(self, address_or_coords=None):
        """Get complete location data with flood risk assessment"""
        try:
            if address_or_coords is None:
                location = self.get_location_by_ip()
            
            elif isinstance(address_or_coords, str):
                location = self.forward_geocode(address_or_coords)
            
            elif isinstance(address_or_coords, (tuple, list)) and len(address_or_coords) == 2:
                lat, lon = address_or_coords
                location = {
                    'latitude': lat,
                    'longitude': lon,
                    'success': True
                }
                
                address = self.reverse_geocode(lat, lon)
                if address:
                    location.update(address)
                
                location['flood_risk_assessment'] = self.assess_flood_risk(
                    lat, lon, 
                    location.get('city')
                )
            
            else:
                return {'success': False, 'error': 'Invalid input'}
            
            return location
            
        except Exception as e:
            return {'success': False, 'error': str(e)}


# Create global instance
location_tracker = LocationTracker()


import json
import csv
import math
import os

# Configuration
CENTER_LAT = 12.500
CENTER_LON = 76.500
RADIUS_DEG = 0.005  # Approx 500m radius
NUM_POINTS = 100
MAX_DEPTH = 10
SURFACE_ELEV = 100

def generate_data():
    # 1. Generate Boundary (Circular Polygon)
    boundary_coords = []
    points = 20
    for i in range(points + 1): # Close the loop
        angle = math.radians((i / points) * 360)
        lat = CENTER_LAT + RADIUS_DEG * math.sin(angle)
        lon = CENTER_LON + RADIUS_DEG * math.cos(angle)
        boundary_coords.append([lon, lat]) # GeoJSON is [lon, lat]

    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Demo Reservoir"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [boundary_coords]
                }
            }
        ]
    }

    with open('demo_boundary.json', 'w') as f:
        json.dump(geojson, f, indent=2)

    # 2. Generate Bathymetry (Bowl shape)
    # Generate a grid of points
    csv_data = []
    
    steps = int(math.sqrt(NUM_POINTS))
    step_size = (RADIUS_DEG * 2) / steps
    
    start_lat = CENTER_LAT - RADIUS_DEG
    start_lon = CENTER_LON - RADIUS_DEG
    
    with open('demo_bathymetry.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['lat', 'lon', 'elevation'])
        
        for i in range(steps):
            for j in range(steps):
                lat = start_lat + i * step_size
                lon = start_lon + j * step_size
                
                # Check distance from center
                dist = math.sqrt((lat - CENTER_LAT)**2 + (lon - CENTER_LON)**2)
                
                if dist <= RADIUS_DEG:
                    # Parabolic depth: z = r^2
                    # Normalized distance (0 to 1)
                    norm_dist = dist / RADIUS_DEG
                    
                    # Depth increases as we get closer to center (norm_dist -> 0)
                    # Elev = Surface - MaxDepth * (1 - norm_dist^2) -- Bowl shape
                    depth = MAX_DEPTH * (1 - norm_dist**2)
                    elev = SURFACE_ELEV - depth
                    
                    writer.writerow([round(lat, 6), round(lon, 6), round(elev, 2)])

if __name__ == "__main__":
    generate_data()
    print("Files created: demo_boundary.json and demo_bathymetry.csv")

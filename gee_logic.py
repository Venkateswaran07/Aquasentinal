import ee
import os

# Set your Google Cloud Project ID here if you encounter permission errors
# Example: GOOGLE_CLOUD_PROJECT = 'my-project-id'
GOOGLE_CLOUD_PROJECT = 'neat-encoder-477511-b8'

# Try to use service account credentials if available
SERVICE_ACCOUNT_KEY = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', None) 

def initialize_gee():
    """Initializes Google Earth Engine."""
    try:
        # Check if already initialized
        try:
            ee.data.getInfo()
            print("Google Earth Engine already initialized")
            return
        except:
            pass
        
        # Attempt to initialize with project ID
        if GOOGLE_CLOUD_PROJECT:
            print(f"Attempting to initialize GEE with project: {GOOGLE_CLOUD_PROJECT}")
            ee.Initialize(project=GOOGLE_CLOUD_PROJECT, opt_url='https://earthengine-highvolume.googleapis.com')
            print(f"Google Earth Engine initialized successfully with project: {GOOGLE_CLOUD_PROJECT}")
        else:
            ee.Initialize()
            print("Google Earth Engine initialized successfully (default project).")
    except ee.EEException as e:
        error_msg = str(e)
        print(f"Warning: GEE Initialization failed: {e}")
        
        # Provide guidance for permission errors
        if "permission" in error_msg.lower() or "does not have required" in error_msg.lower():
            print("\n=== PERMISSION ERROR DETECTED ===")
            print("To fix this error:")
            print(f"1. Go to: https://console.cloud.google.com/welcome?project={GOOGLE_CLOUD_PROJECT}")
            print("2. Enable 'Earth Engine API' in the APIs & Services")
            print("3. Create a Service Account or grant your user the required roles:")
            print("   - roles/earthengine.admin or roles/earthengine.viewer")
            print("4. Re-authenticate using: earthengine authenticate")
            print("=================================\n")
        
        raise
    except Exception as e:
        print(f"Warning: Unexpected error during GEE init: {e}")
        raise

def analyze_water(lat, lon):
    """
    Analyzes water at a specific location using Sentinel-2 data.
    Returns estimated area (km2) and volume (MCM).
    """
    try:
        # Define a region of interest (ROI) - buffer around point
        point = ee.Geometry.Point([lon, lat])
        roi = point.buffer(2000) # 2km radius analysis window

        # Get Sentinel-2 Image collection
        # Filter by date (recent) and cloud cover
        dataset = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                  .filterBounds(roi) \
                  .filterDate('2023-01-01', '2026-01-18') \
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
                  .sort('system:time_start', False) # Get latest

        image = dataset.first()
        
        if not image:
            print("No suitable satellite image found.")
            return {"area": 0, "volume": 0, "error": "No image found"}

        # Calculate NDWI (Normalized Difference Water Index)
        # NDWI = (Green - NIR) / (Green + NIR)
        # S2 Bands: B3 (Green), B8 (NIR)
        ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI')

        # Threshold NDWI to get water mask (> 0.1 usually water)
        water_mask = ndwi.gt(0.1).rename('Water')
        
        # Calculate Area
        # Multiply pixel count by pixel area
        pixel_area = ee.Image.pixelArea()
        water_area_image = pixel_area.mask(water_mask)
        
        # Reduce region to get sum of area
        stats = water_area_image.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=roi,
            scale=10,
            maxPixels=1e9
        )
        
        area_sq_meters = stats.get('area').getInfo()
        
        if area_sq_meters is None:
             return {"area": 0, "volume": 0}

        area_km2 = area_sq_meters / 1e6
        
        # Volume Estimation Heuristic
        # Simple relationship: Volume = Area * Depth
        # Without bathymetry, we assume a characteristic depth function or constant
        # For prototype: Depth ~ random factor or log of area? 
        # Let's use a simplified logical depth: larger lakes are deeper.
        # Depth approx = 5m + (Area * 0.5) up to max 50m (Pure heuristic)
        estimated_depth_m = min(50, 5 + (area_km2 * 0.5)) 
        
        volume_mcm = (area_km2 * estimated_depth_m) # 1 km2 * 1 m = 1 MCM (Wait, 1 km2 * 1m = 1,000,000 m3 = 1 MCM)
        
        return {
            "area": round(area_km2, 2),
            "volume": round(volume_mcm, 2),
            "date": image.date().format('YYYY-MM-dd').getInfo()
        }

    except Exception as e:
        print(f"GEE Error: {e}")
        return {"area": 0, "volume": 0, "error": str(e)}

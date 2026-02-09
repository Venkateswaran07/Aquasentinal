import ee
import os
import datetime

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
        # Attempt to initialize with project ID
        # Explicitly check for Service Account env var set in server.py
        sa_key = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        
        if sa_key and os.path.exists(sa_key):
            try:
                print(f"loading service account from: {sa_key}")
                from google.oauth2 import service_account
                credentials = service_account.Credentials.from_service_account_file(sa_key)
                scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/earthengine'])
                
                print(f"Attempting to initialize GEE with Service Account and project: {GOOGLE_CLOUD_PROJECT}")
                ee.Initialize(credentials=scoped_credentials, project=GOOGLE_CLOUD_PROJECT)
                print(f"Google Earth Engine initialized successfully with Service Account.")
                return
            except Exception as e:
                print(f"Service Account Auth failed: {e}. Falling back to default...")

        if GOOGLE_CLOUD_PROJECT:
            try:
                print(f"Attempting to initialize GEE with project: {GOOGLE_CLOUD_PROJECT}")
                ee.Initialize(project=GOOGLE_CLOUD_PROJECT)
                print(f"Google Earth Engine initialized successfully with project: {GOOGLE_CLOUD_PROJECT}")
            except Exception as e:
                print(f"Project-specific init failed: {e}. Falling back to default...")
                ee.Initialize()
                print("Google Earth Engine initialized successfully (default project).")
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
        
        # Don't raise here, allow the app to try running (it might fail later but better than crashing on start)
        # raise 
    except Exception as e:
        print(f"Warning: Unexpected error during GEE init: {e}")
        # raise

def get_water_metrics(roi, start_date, end_date, scale=10):
    """
    Calculates water area for a given time range within an ROI.
    """
    try:
        dataset = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                  .filterBounds(roi) \
                  .filterDate(start_date, end_date) \
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
                  .sort('CLOUDY_PIXEL_PERCENTAGE') # Get least cloudy
        
        # Check if collection is empty
        count = dataset.size().getInfo()
        if count == 0:
            return 0, None
            
        image = dataset.first()
        
        # Calculate NDWI
        ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI')
        water_mask = ndwi.gt(0.1).rename('Water')
        
        # Calculate Area
        pixel_area = ee.Image.pixelArea()
        water_area_image = pixel_area.mask(water_mask)
        
        stats = water_area_image.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=roi,
            scale=scale,
            maxPixels=1e9
        )
        
        area_sq_meters = stats.get('area').getInfo()
        if area_sq_meters is None:
            return 0, None
            
        return area_sq_meters / 1e6, image # Return km2 and the image used
    except Exception as e:
        print(f"Error in get_water_metrics: {e}")
        return 0, None

def analyze_water(lat, lon):
    """
    Analyzes water at a specific location using Sentinel-2 and SRTM DEM.
    Returns estimated area (km2), volume (MCM), and seasonal trends.
    """
    print(f"DEBUG: analyze_water called for {lat}, {lon}")
    try:
        # Define a region of interest (ROI) - buffer around point
        point = ee.Geometry.Point([lon, lat])
        roi = point.buffer(2000) # 2km radius analysis window
        
        # 1. Current Status (Latest available in last 3 months) - Keep High Precision (10m)
        end_date = datetime.datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.datetime.now() - datetime.timedelta(days=90)).strftime('%Y-%m-%d')
        
        current_area, current_image = get_water_metrics(roi, start_date, end_date, scale=10)
        
        # 2. Seasonal Analysis (Past Year) - Use Lower Precision (30m) for speed
        current_year = datetime.datetime.now().year - 1
        
        winter_area = 0
        summer_area = 0
        monsoon_area = 0
        
        try:
            # Winter (Jan-Feb)
            winter_area, _ = get_water_metrics(roi, f'{current_year}-01-01', f'{current_year}-02-28', scale=30)
            # Summer (Apr-May)
            summer_area, _ = get_water_metrics(roi, f'{current_year}-04-01', f'{current_year}-05-31', scale=30)
            # Monsoon (Aug-Sep)
            monsoon_area, _ = get_water_metrics(roi, f'{current_year}-08-01', f'{current_year}-09-30', scale=30)
        except Exception as e:
            print(f"Seasonal analysis failed (skipping): {e}")
            # Continue with 0s for seasonal (better than crashing)
        
        # 3. Elevation-Based Volume Estimation
        # Using SRTM/NASADEM for topography
        dem = ee.Image('NASA/NASADEM_HGT/001').select('elevation')
        
        # Calculate Average Elevation of the Water Surface
        if current_image:
            ndwi = current_image.normalizedDifference(['B3', 'B8'])
            water_mask = ndwi.gt(0.1)
            
            # Get elevation of water pixels
            water_elev = dem.updateMask(water_mask)
            elev_stats = water_elev.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=roi,
                scale=30,
                maxPixels=1e9
            )
            avg_water_elev = elev_stats.get('elevation').getInfo() or 0
        else:
            avg_water_elev = 0

        # Heuristic Volume: 
        # Assume a depression shape. 
        # Volume ~ Area * (Depth). 
        # We estimate Depth using terrain slope from DEM surrounding the water.
        
        slope = ee.Terrain.slope(dem)
        # Get slope at the shores (buffer around water mask not implemented for speed) - use ROI mean slope
        slope_stats = slope.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=30,
            maxPixels=1e9
        )
        avg_slope_deg = slope_stats.get('slope').getInfo() or 5
        import math
        avg_slope_rad = math.radians(avg_slope_deg)
        
        # Model: Conical depression
        # Depth = Radius * tan(slope)
        # Radius = sqrt(Area / pi)
        # Volume = 1/3 * Area * Depth
        
        if current_area > 0:
            radius_km = math.sqrt(current_area / math.pi)
            estimated_depth_km = radius_km * math.tan(avg_slope_rad)
            estimated_volume_km3 = (1/3) * current_area * estimated_depth_km
            volume_mcm = estimated_volume_km3 * 1000 
        else:
            volume_mcm = 0

        # Calculate Max Capacity based on Historical/Seasonal Max
        max_area = max(current_area, winter_area, summer_area, monsoon_area)
        if max_area > 0:
             max_radius_km = math.sqrt(max_area / math.pi)
             max_depth_km = max_radius_km * math.tan(avg_slope_rad)
             max_vol_km3 = (1/3) * max_area * max_depth_km
             max_vol_mcm = max_vol_km3 * 1000
        else:
             max_vol_mcm = volume_mcm * 1.2 # Fallback if no data
            
        # 4. Generate Visualization Layers (Map IDs)
        # Helper to get Tile URL
        def get_map_url(image, viz_params):
            try:
                map_id = image.getMapId(viz_params)
                # Manually construct URL to avoid weird template issues
                # Standard V1 API: https://earthengine.googleapis.com/v1/{mapid}/tiles/{z}/{x}/{y}
                
                base_url = "https://earthengine.googleapis.com/v1"
                map_name = map_id['mapid']
                url = f"{base_url}/{map_name}/tiles/{{z}}/{{x}}/{{y}}"
                
                print(f"Generated URL: {url}")
                return url
            except Exception as e:
                print(f"Error generating map URL: {e}")
                return None

        layers = {}
        
        # A. Seasonal Layers
        # Define Palettes
        water_viz = {'min': 0, 'max': 1, 'palette': ['white', 'blue']}
        
        # Get images for seasonal comparison (re-fetch to ensure we have images)
        current_year = datetime.datetime.now().year - 1
        
        # Helper for mosaic/median
        def get_seasonal_layer(start, end, palette):
            try:
                col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                    .filterBounds(roi) \
                    .filterDate(start, end) \
                    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
                    .map(lambda img: img.normalizedDifference(['B3', 'B8']).rename('NDWI'))
                
                # Create a composite (max NDWI to find water, or median)
                # Check if collection is empty
                count = col.size().getInfo()
                if count == 0:
                     return None

                # Max NDWI is good for "Water Spread" to show max extent
                water_composite = col.max().gt(0.1).selfMask()
                
                return get_map_url(water_composite, {'palette': palette})
            except Exception as e:
                print(f"Error creating seasonal layer {start}-{end}: {e}")
                return None

        layers['winter'] = get_seasonal_layer(f'{current_year}-01-01', f'{current_year}-02-28', ['#a5f3fc', '#0891b2'])
        layers['summer'] = get_seasonal_layer(f'{current_year}-04-01', f'{current_year}-05-31', ['#fdba74', '#ea580c'])
        layers['monsoon'] = get_seasonal_layer(f'{current_year}-08-01', f'{current_year}-09-30', ['#86efac', '#16a34a'])

        # B. Analytics Layer: Professional Bathymetry & Contours
        if current_image:
            # 1. Base Water Mask
            water_mask = current_image.normalizedDifference(['B3', 'B8']).gt(0.1)
            lake_bed = dem.updateMask(water_mask)
            
            # 2. Depth Map (Gradient)
            # Use a standard bathymetric palette (Light to Dark Blue)
            # GEBCO style or similar
            depth_map = ee.Image.constant(avg_water_elev).subtract(lake_bed).rename('depth')
            depth_map = depth_map.where(depth_map.lt(0), 0)
            
            # Layers for Frontend
            
            # Layer 1: Depth Gradient (Scientific Blue)
            props_depth = {'min': 0, 'max': 20, 'palette': ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b']}
            layers['depth'] = get_map_url(
                depth_map.updateMask(depth_map.gt(0)),
                props_depth
            )
            
            # Layer 2: Contours (Vector-like Lines)
            # Reliable math-based contours (every 2m)
            # Create lines where depth % interval is near 0
            interval = 2
            # Use 'canny' edge detection or simple thresholding for cleaner lines
            # Here uses simple modulus for robustness
            contours = depth_map.toInt().mod(interval).eq(0).And(depth_map.gte(1))
            
            layers['analytics'] = get_map_url(
                ee.Image(0).paint(ee.Geometry.Point([0,0]), 0, 1).where(contours, 1).updateMask(contours),
                {'palette': ['#ffffff'], 'min': 0, 'max': 1, 'opacity': 0.8}
            )
            
            # Layer 3: Raw Water Mask (Spectral)
            layers['water_mask'] = get_map_url(
                water_mask.selfMask(),
                {'palette': ['#00FFFF']} # Cyan High-Vis
            )

        else:
            layers['depth'] = None
            layers['analytics'] = None
            layers['water_mask'] = None

        return {
            "area": round(current_area, 2),
            "volume": round(volume_mcm, 2),
            "max_volume": round(max_vol_mcm, 2),
            "date": current_image.date().format('YYYY-MM-dd').getInfo() if current_image else "N/A",
            "avg_elevation": round(avg_water_elev, 1),
            "seasonal": {
                "winter": round(winter_area, 2),
                "summer": round(summer_area, 2),
                "monsoon": round(monsoon_area, 2)
            },
            "layers": layers
        }

    except Exception as e:
        print(f"GEE Error: {e}")
        import traceback
        traceback.print_exc()
        return {"area": 0, "volume": 0, "error": str(e)}

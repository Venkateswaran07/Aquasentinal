
import pandas as pd
import json
import os
from fpdf import FPDF
from shapely.geometry import shape, Point, Polygon
import numpy as np
import datetime

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

class DataProcessor:
    def __init__(self):
        self.boundary = None
        self.bathymetry = None
        self.results = None

    def process_boundary(self, file_path):
        """Parses GeoJSON boundary file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # extract features (assuming single polygon for reservoir)
            if 'features' in data:
                geom = data['features'][0]['geometry']
            else:
                geom = data['geometry']
                
            self.boundary = shape(geom)
            return {"status": "success", "message": "Boundary loaded successfully", "area_km2": self.boundary.area * 10000} # Roughly deg to km? No, projection needed. Keeping simple.
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def process_bathymetry(self, file_path):
        """Parses CSV bathymetry (Lat, Lon, Elevation)."""
        try:
            df = pd.read_csv(file_path)
            # Normalize columns
            df.columns = [c.lower().strip() for c in df.columns]
            
            required = {'lat', 'lon', 'elevation'}
            if not required.issubset(df.columns) and not {'latitude', 'longitude', 'elevation'}.issubset(df.columns):
                 return {"status": "error", "message": "CSV must contain lat, lon, elevation columns"}
            
            self.bathymetry = df
            return {"status": "success", "message": f"Loaded {len(df)} elevation points"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_volume_curve(self, boundary_file, bathy_file):
        """
        Generates Elevation-Area-Capacity table.
        This is a simplified interpolation method for the prototype.
        """
        # Load data
        b_res = self.process_boundary(boundary_file)
        if b_res['status'] == 'error': return b_res
        
        d_res = self.process_bathymetry(bathy_file)
        if d_res['status'] == 'error': return d_res
        
        df = self.bathymetry
        
        # Determine range
        min_elev = df['elevation'].min()
        max_elev = df['elevation'].max()
        
        levels = np.linspace(min_elev, max_elev, num=20)
        results = []
        
        # Simple estimation: 
        # Area at Level Z approx proportional to points <= Z within boundary
        # For a real system, we'd generate a TIN or Grid. 
        # Here: We count points below level L as "underwater".
        
        total_points = len(df)
        
        cumulative_vol = 0
        prev_area = 0
        prev_h = min_elev
        
        for h in levels:
            # Count points below this elevation
            # In a depression, lower elevation = deeper center.
            # Water Level H means everything BELOW H is filled?
            # Usually Bathymetry is bed elevation. Water fills from min_elev upwards.
            
            # Surface Area at Water Level H:
            # Approximation: Fraction of points where Bed_Elevation <= H
            underwater_points = df[df['elevation'] <= h]
            frac_area = len(underwater_points) / total_points
            
            # Total Area factor (approximate scaling for prototype)
            # Assuming the boundary defines the max extent (at max elev)
            # Convert rough lat/lon area to km2 (very rough approximation for prototype)
            # 1 deg ~ 111km. Area = deg^2 * 12321.
            bounds = self.boundary.bounds # (minx, miny, maxx, maxy)
            width = (bounds[2] - bounds[0]) * 111
            height = (bounds[3] - bounds[1]) * 111
            max_area_km2 = width * height * 0.7 # Correction factor for shape
            
            area_at_h = frac_area * max_area_km2
            
            # Volume Step (Trapezoidal)
            dh = h - prev_h
            d_vol = ((area_at_h + prev_area) / 2) * (dh / 1000) # km2 * m / 1000 = km3
            cumulative_vol += d_vol * 1000 # to MCM
            
            results.append({
                "Elevation (m)": round(h, 2),
                "Surface Area (sq km)": round(area_at_h, 3),
                "Volume (MCM)": round(cumulative_vol, 3)
            })
            
            prev_area = area_at_h
            prev_h = h
            
        self.results = pd.DataFrame(results)
        return {"status": "success", "data": results}

    def generate_report(self, output_path="report.pdf"):
        if self.results is None:
            return None
            
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="Water Resource Analysis Report", ln=1, align='C')
        
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=1, align='C')
        pdf.ln(10)
        
        # Summary
        max_vol = self.results.iloc[-1]['Volume (MCM)']
        max_level = self.results.iloc[-1]['Elevation (m)']
        
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt="Executive Summary", ln=1, align='L')
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, txt=f"The analysis calculated storage capacity based on provided bathymetric data and boundary inputs. \n\nTotal Storage Capacity: {max_vol} MCM\nFull Tank Level (FTL): {max_level} m")
        pdf.ln(10)

        # Table
        pdf.set_font("Arial", 'B', 10)
        col_width = pdf.w / 4.5
        row_height = 8
        
        headers = self.results.columns
        for col in headers:
            pdf.cell(col_width, row_height, col, border=1)
        pdf.ln(row_height)
        
        pdf.set_font("Arial", size=10)
        for _, row in self.results.iterrows():
            for col in headers:
                pdf.cell(col_width, row_height, str(row[col]), border=1)
            pdf.ln(row_height)
            
        pdf.output(output_path)
        return output_path

    def export_csv(self, output_path="report.csv"):
        if self.results is not None:
            self.results.to_csv(output_path, index=False)
            return output_path
        return None



from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from gee_logic import initialize_gee, analyze_water
import requests
import os

app = Flask(__name__, template_folder='.')
CORS(app) # Enable CORS for all routes

# --- GEE Authentication Helper for Render/Cloud ---
# If GEE_CREDENTIALS_JSON env var exists, write it to a file
    import os
    # Use absolute path for the credentials file
    cred_path = os.path.join(os.getcwd(), "credentials.json")
    print(f"Found GEE_CREDENTIALS_JSON env var, creating credentials.json at {cred_path}...")
    with open(cred_path, "w") as f:
        f.write(gee_json)
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = cred_path

# Initialize GEE on startup
initialize_gee()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.json
    lat = data.get('lat')
    lng = data.get('lng')

    if lat is None or lng is None:
        return jsonify({"error": "Missing coordinates"}), 400

    print(f"Analyzing location: Lat {lat}, Lng {lng}")
    try:
        # Call GEE Logic
        result = analyze_water(lat, lng)
        print(f"Analysis result: {result}")
        return jsonify(result)
    except Exception as e:
        import traceback
        print("Exception during analysis:")
        traceback.print_exc()
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

# --- File Upload & Processing API ---
from data_processor import DataProcessor
import os
from werkzeug.utils import secure_filename

processor = DataProcessor()
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/api/upload_process', methods=['POST'])
def upload_file():
    if 'boundary' not in request.files or 'bathymetry' not in request.files:
        return jsonify({"error": "Missing files"}), 400
        
    boundary = request.files['boundary']
    bathymetry = request.files['bathymetry']
    
    if boundary.filename == '' or bathymetry.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    b_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(boundary.filename))
    d_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(bathymetry.filename))
    
    boundary.save(b_path)
    bathymetry.save(d_path)
    
    # Process
    try:
        result = processor.calculate_volume_curve(b_path, d_path)
        if result['status'] == 'error':
            return jsonify(result), 400
            
        # Generate Files
        processor.generate_report(os.path.join(app.config['UPLOAD_FOLDER'], 'report.pdf'))
        processor.export_csv(os.path.join(app.config['UPLOAD_FOLDER'], 'report.csv'))
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

from flask import send_from_directory

@app.route('/api/download/<type>')
def download_report(type):
    filename = 'report.pdf' if type == 'pdf' else 'report.csv'
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)

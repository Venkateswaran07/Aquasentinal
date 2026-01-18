from flask import Flask, render_template, request, jsonify
from gee_logic import initialize_gee, analyze_water

app = Flask(__name__, template_folder='.')

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
    
    # Call GEE Logic
    result = analyze_water(lat, lng)
    
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)

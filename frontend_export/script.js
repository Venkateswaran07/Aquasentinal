
// --- Constants & Config ---
// Mock API or configuration here
const API_BASE_URL = "http://localhost:5000";

// --- Global State ---
const state = {
    map: null,
    marker: null,
    layerGroup: null,
    drawControl: null,
    drawnItems: null,
    mode: 'click', // click, draw
    currentLat: 0,
    currentLng: 0,
    isScanning: false,
    layers: {}
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    // Default Mode
    setMode('click');
});

// --- Map Logic ---
function initMap() {
    try {
        state.map = L.map('map', {
            rotate: true,
            touchZoom: true,
            zoomControl: false
        }).setView([12.4244, 76.5761], 13); // Default view

        L.control.zoom({ position: 'bottomright' }).addTo(state.map);

        // Satellite Basemap (Esri)
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Tiles &copy; Esri',
            className: 'map-tiles'
        }).addTo(state.map);

        // Optional Labels
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
            opacity: 0.6
        }).addTo(state.map);

        state.layerGroup = L.layerGroup().addTo(state.map);
        state.drawnItems = new L.FeatureGroup();
        state.map.addLayer(state.drawnItems);

        // Initialize Draw Control (if needed)
        state.drawControl = new L.Control.Draw({
            draw: {
                polygon: {
                    allowIntersection: false,
                    showArea: true,
                    shapeOptions: { color: '#06b6d4', className: 'glow-shape', weight: 2, opacity: 1, fillOpacity: 0.1 }
                },
                rectangle: { shapeOptions: { color: '#06b6d4', weight: 2, fillOpacity: 0.1 } },
                circle: false, marker: false, polyline: false, circlemarker: false
            },
            edit: { featureGroup: state.drawnItems, remove: true }
        });

        // Events
        state.map.on('click', onMapClick);
        state.map.on(L.Draw.Event.CREATED, (e) => {
            const layer = e.layer;
            state.drawnItems.clearLayers();
            state.drawnItems.addLayer(layer);
            const center = layer.getBounds().getCenter();
            onMapClick({ latlng: center, isDraw: true });
        });

    } catch (err) {
        console.error("Map Init Failed:", err);
    }
}

// --- Interaction Logic ---
function setMode(mode) {
    state.mode = mode;
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.remove('bg-cyan-500', 'text-white', 'border-cyan-400');
        btn.classList.add('bg-slate-800/50', 'text-slate-300', 'border-slate-700');
    });

    const activeBtn = document.getElementById(`btn-mode-${mode}`);
    if (activeBtn) {
        activeBtn.classList.remove('bg-slate-800/50', 'text-slate-300', 'border-slate-700');
        activeBtn.classList.add('bg-cyan-500', 'text-white', 'border-cyan-400');
    }

    if (mode === 'draw') {
        state.map.addControl(state.drawControl);
        showToast("Draw Mode: Create a polygon to scan.");
    } else {
        state.map.removeControl(state.drawControl);
        showToast("Click Mode: Click to target location.");
    }
}

function onMapClick(e) {
    if (state.isScanning) return;
    if (state.mode === 'draw' && !e.isDraw) return;

    state.currentLat = e.latlng.lat;
    state.currentLng = e.latlng.lng;

    // Update UI
    document.getElementById('dispLat').innerText = state.currentLat.toFixed(5);
    document.getElementById('dispLon').innerText = state.currentLng.toFixed(5);

    // Marker Animation
    state.layerGroup.clearLayers();
    const rippleIcon = L.divIcon({
        className: 'ripple-icon',
        iconSize: [20, 20],
        iconAnchor: [10, 10]
    });
    L.marker([state.currentLat, state.currentLng], { icon: rippleIcon }).addTo(state.layerGroup);

    startAnalysis();
}

let scanController = null;

// Real Analysis Function
async function startAnalysis() {
    state.isScanning = true;
    const overlay = document.getElementById('scanning-overlay');
    const statusText = document.getElementById('scan-status');

    overlay.style.display = 'flex';
    statusText.innerText = "Connecting to Satellite Network...";

    try {
        // 1. Send Request to Backend
        statusText.innerText = "Acquiring Multispectral Imagery...";

        const response = await fetch(`${API_BASE_URL}/api/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                lat: state.currentLat,
                lng: state.currentLng
            })
        });

        statusText.innerText = "Processing GEE Algorithms...";

        if (!response.ok) {
            throw new Error(`Analysis Failed: ${response.statusText}`);
        }

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        // 2. Update UI with Real Data
        statusText.innerText = "Finalizing Report...";
        updateMetrics(data);
        updateLayers(data.layers);

        showToast("Analysis Complete", "success");

    } catch (err) {
        console.error(err);
        showToast(`Error: ${err.message}`, "error");
        statusText.innerText = "ERROR";
    } finally {
        // Hide Overlay
        setTimeout(() => {
            overlay.style.display = 'none';
            state.isScanning = false;
        }, 800);
    }
}

function updateLayers(layers) {
    if (!layers) return;

    // Clear previous analysis layers
    state.layerGroup.clearLayers();
    // Re-add marker
    const rippleIcon = L.divIcon({
        className: 'ripple-icon',
        iconSize: [20, 20],
        iconAnchor: [10, 10]
    });
    L.marker([state.currentLat, state.currentLng], { icon: rippleIcon }).addTo(state.layerGroup);

    // Setup Layer Controls
    const layerControlDiv = document.getElementById('layerControl');
    const layerControlPanel = document.getElementById('layerControlPanel');
    layerControlDiv.innerHTML = ''; // Clear old controls

    // Helper to add a layer toggle
    const addLayerToggle = (id, name, url, color) => {
        if (!url) return;

        // Create Layer
        const layer = L.tileLayer(url, { opacity: 0.8 });

        // Create UI Toggle
        const div = document.createElement('div');
        div.className = "flex items-center gap-3 p-2 rounded bg-slate-800/50 hover:bg-slate-700/50 cursor-pointer transition-colors";
        div.innerHTML = `
            <input type="checkbox" id="toggle-${id}" class="w-4 h-4 rounded border-slate-600 text-cyan-500 focus:ring-offset-0 bg-slate-700">
            <div class="w-3 h-3 rounded-full" style="background-color: ${color}"></div>
            <span class="text-sm font-medium text-slate-300">${name}</span>
        `;

        const checkbox = div.querySelector('input');

        // Event Listener
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                state.layerGroup.addLayer(layer);
            } else {
                state.layerGroup.removeLayer(layer);
            }
        });

        layerControlDiv.appendChild(div);
    };

    // Add specific layers based on GEE response
    if (layers.water_mask) addLayerToggle('water', 'Current Water Extent', layers.water_mask, '#00FFFF');
    if (layers.depth) addLayerToggle('depth', 'Bathymetry (Depth)', layers.depth, '#08519c');
    if (layers.analytics) addLayerToggle('contour', 'Depth Contours', layers.analytics, '#ffffff');

    if (layers.winter) addLayerToggle('winter', 'Winter Extent', layers.winter, '#0891b2');
    if (layers.summer) addLayerToggle('summer', 'Summer Extent', layers.summer, '#ea580c');
    if (layers.monsoon) addLayerToggle('monsoon', 'Monsoon Extent', layers.monsoon, '#16a34a');

    // Show panel
    layerControlPanel.classList.remove('hidden');
}

function cancelScanning() {
    document.getElementById('scanning-overlay').style.display = 'none';
    state.isScanning = false;
    showToast("Cancelled.", "info");
}

function updateMetrics(data) {
    document.getElementById('metricArea').innerText = data.area + " km²";
    document.getElementById('metricVolume').innerText = data.volume + " MCM";

    // Fill Bar Logic
    const capacity = data.max_volume || data.volume * 1.5;
    const fillPct = Math.min(100, Math.round((data.volume / capacity) * 100));
    const fillBar = document.getElementById('fillBar');
    fillBar.style.width = `${fillPct}%`;
    document.getElementById('fillPct').innerText = `${fillPct}%`;

    // Color
    fillBar.className = `h-2 rounded-full transition-all duration-1000 ${fillPct < 30 ? 'bg-red-500' : fillPct > 80 ? 'bg-blue-500' : 'bg-cyan-500'}`;

    document.getElementById('metricElev').innerText = `${data.avg_elevation}m`;
}

// Navigation
function navTo(id) {
    document.querySelectorAll('section').forEach(el => el.classList.add('hidden'));
    document.getElementById(id).classList.remove('hidden');

    document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('text-cyan-400', 'border-b-2', 'border-cyan-400'));
    document.getElementById(`nav-${id}`).classList.add('text-cyan-400', 'border-b-2', 'border-cyan-400');

    if (id === 'dashboard' && state.map) setTimeout(() => state.map.invalidateSize(), 200);
}

function showToast(msg, type = 'info') {
    const toast = document.getElementById('toast-notification');
    if (toast) {
        toast.innerText = msg;
        toast.classList.remove('translate-y-20', 'opacity-0');
        setTimeout(() => toast.classList.add('translate-y-20', 'opacity-0'), 3000);
    }
}

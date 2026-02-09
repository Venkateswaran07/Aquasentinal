
// --- Constants & Config ---
const apiURL = (typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '') + '/api/gemini';

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
    currentArea: 0,
    currentVol: 0,
    isScanning: false,
    layers: {},
    charts: {} // Store chart instances
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    initCharts();
    setupDropzones();

    // Default Mode
    setMode('click');
});

// --- Map Logic ---
function initMap() {
    try {
        // Dark Mode Map Styling - Using CartoDB Dark Matter for the base, then Overlay Satellite
        state.map = L.map('map', {
            rotate: true,
            touchZoom: true,
            zoomControl: false
        }).setView([12.4244, 76.5761], 13);

        // Reposition Zoom Control
        L.control.zoom({
            position: 'bottomright'
        }).addTo(state.map);

        // Base Layer: Satellite (Esri)
        // We use a dark filter on the map container in CSS if needed, but here we just load standard satellite
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Tiles &copy; Esri',
            className: 'map-tiles'
        }).addTo(state.map);

        // Labels (Optional)
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
            opacity: 0.6
        }).addTo(state.map);

        state.layerGroup = L.layerGroup().addTo(state.map);
        state.drawnItems = new L.FeatureGroup();
        state.map.addLayer(state.drawnItems);

        // Draw Control
        state.drawControl = new L.Control.Draw({
            draw: {
                polygon: {
                    allowIntersection: false,
                    showArea: true,
                    shapeOptions: {
                        color: '#06b6d4',
                        className: 'glow-shape',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.1
                    }
                },
                rectangle: {
                    shapeOptions: {
                        color: '#06b6d4',
                        weight: 2,
                        fillOpacity: 0.1
                    }
                },
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

    // Update UI Buttons
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
        showToast("Draw Mode: Create a polygon to analyze the area.");
    } else {
        state.map.removeControl(state.drawControl);
        showToast("Click Mode: Click anywhere to analyze.");
    }
}

function onMapClick(e) {
    if (state.isScanning) return;
    if (state.mode === 'draw' && !e.isDraw) return;

    state.currentLat = e.latlng.lat;
    state.currentLng = e.latlng.lng;

    // Update Coordinates Display
    document.getElementById('dispLat').innerText = state.currentLat.toFixed(5);
    document.getElementById('dispLon').innerText = state.currentLng.toFixed(5);

    // Visual Feedback
    state.layerGroup.clearLayers();

    const rippleIcon = L.divIcon({
        className: 'ripple-icon',
        iconSize: [20, 20],
        iconAnchor: [10, 10]
    });
    L.marker([state.currentLat, state.currentLng], { icon: rippleIcon }).addTo(state.layerGroup);

    // 2km Radius Visual - DISABLED per user request
    // L.circle([state.currentLat, state.currentLng], {
    //     radius: 2000,
    //     color: '#06b6d4',
    //     weight: 1,
    //     fillColor: '#06b6d4',
    //     fillOpacity: 0.05,
    //     dashArray: '10, 10'
    // }).addTo(state.layerGroup);

    startScanning();
}

let scanController = null;

async function startScanning() {
    state.isScanning = true;
    const statusText = document.getElementById('scan-status');
    const overlay = document.getElementById('scanning-overlay');

    // UI: Start Scan
    overlay.style.display = 'flex';
    statusText.innerText = "Analyzing Satellite Data...";
    statusText.classList.remove('text-red-500'); // Reset error state

    // Setup AbortController
    if (scanController) scanController.abort();
    scanController = new AbortController();

    try {
        const response = await fetch(`${API_BASE_URL}/api/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat: state.currentLat, lng: state.currentLng }),
            signal: scanController.signal
        });

        if (!response.ok) throw new Error("Analysis Service Failed");
        const data = await response.json();

        if (data.error) throw new Error(data.error);

        // Success
        state.currentArea = data.area;
        state.currentVol = data.volume;
        state.layers = data.layers;

        updateMetrics(data);
        updateCharts(data.volume, data.seasonal);
        updateLayerControl(data.layers);

        statusText.innerText = "Complete.";
        showToast("Analysis Complete.", "success");

        // Hide overlay on success
        setTimeout(() => {
            overlay.style.display = 'none';
            state.isScanning = false;
        }, 500);

    } catch (err) {
        if (err.name === 'AbortError') {
            console.log('Analysis cancelled by user');
            showToast("Analysis Cancelled", "info");
        } else {
            console.error(err);
            const errMsg = err.message || "Unknown Error";
            showToast("Analysis Failed: " + errMsg, "error");
            statusText.innerText = "Error.";
            statusText.classList.add('text-red-500');
        }
    } finally {
        if (state.isScanning && (!scanController || !scanController.signal.aborted)) {
            // If we are still 'isScanning' but not aborted, it means we finished naturally (success or error)
            // But valid success hides itself. Errors show text. 
            // We only FORCE hide here if something went wrong but we want to reset UI eventually?
            // For now, let specific blocks handle it. 
            // IMPORTANT: If error, force hide after delay
            // checks if error occurred? 
            // Simple logic: if still scanning after all, hide it.
        }
        // Ensure overlay hides on error/cancel eventually if not handled
        // If aborted, we hide immediately in cancel function, so this is fallback
    }
}

function cancelScanning() {
    if (scanController) {
        scanController.abort();
        scanController = null;
    }
    document.getElementById('scanning-overlay').style.display = 'none';
    state.isScanning = false;
    state.layerGroup.clearLayers(); // Clear the marker too if cancelled
    showToast("Cancelled.", "info");
}

function updateMetrics(data) {
    // Animate Numbers
    animateValue("metricArea", data.area, " km²");
    animateValue("metricVolume", data.volume, " MCM");

    const capacity = data.max_volume > 0 ? data.max_volume : data.volume * 1.5;
    const fillPct = capacity > 0 ? Math.min(100, Math.round((data.volume / capacity) * 100)) : 0;

    const fillBar = document.getElementById('fillBar');
    fillBar.style.width = `${fillPct}%`;
    document.getElementById('fillPct').innerText = `${fillPct}%`;

    // Colorize Bar
    fillBar.className = `h-2 rounded-full transition-all duration-1000 ${fillPct < 30 ? 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]' :
        fillPct > 80 ? 'bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]' :
            'bg-cyan-500 shadow-[0_0_10px_rgba(6,182,212,0.5)]'
        }`;

    document.getElementById('metricElev').innerText = `${data.avg_elevation}m`;
}

// --- Helpers ---
function animateValue(id, value, suffix) {
    const el = document.getElementById(id);
    el.innerText = value + suffix;
    el.classList.add('text-primary-400');
    setTimeout(() => el.classList.remove('text-primary-400'), 500);
}

function showToast(msg, type = 'info') {
    // Simple toast implementation or console
    console.log(`[${type.toUpperCase()}] ${msg}`);
    const toast = document.getElementById('toast-notification');
    if (toast) {
        toast.innerText = msg;
        toast.classList.remove('translate-y-20', 'opacity-0');
        setTimeout(() => toast.classList.add('translate-y-20', 'opacity-0'), 3000);
    }
}

// --- Layer Control ---
let overlayLayerGroup = null;

function updateLayerControl(layers) {
    if (overlayLayerGroup) state.map.removeLayer(overlayLayerGroup);
    overlayLayerGroup = L.layerGroup().addTo(state.map);

    const container = document.getElementById('layerControl');
    container.innerHTML = ''; // Clear

    const createToggle = (key, label, color, isDefault = false) => {
        if (!layers[key]) return;

        // Custom Styled Checkbox
        const wrap = document.createElement('label');
        wrap.className = "flex items-center space-x-3 cursor-pointer group p-2 rounded hover:bg-white/5 transition-colors";

        const checkedAttr = isDefault ? 'checked' : '';

        wrap.innerHTML = `
            <input type="checkbox" class="checkbox-tech peer hidden" id="chk-${key}" ${checkedAttr}>
            <div class="w-5 h-5 border border-slate-600 rounded flex items-center justify-center bg-slate-800 peer-checked:bg-cyan-500 peer-checked:border-cyan-400 transition-all">
               <svg class="w-3 h-3 text-white opacity-0 peer-checked:opacity-100" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="4"><polyline points="20 6 9 17 4 12"></polyline></svg>
            </div>
            <span class="text-sm text-slate-300 group-hover:text-white">${label}</span>
            <div class="w-2 h-2 rounded-full ml-auto shadow-[0_0_8px]" style="background-color: ${color}; box-shadow: 0 0 8px ${color}"></div>
        `;

        let activeLayer = null;

        const toggleLayer = (isChecked) => {
            if (isChecked) {
                if (activeLayer) overlayLayerGroup.removeLayer(activeLayer);
                // Ensure Analytics Layer is on TOP
                const zIndex = key === 'analytics' ? 10 : 5;
                activeLayer = L.tileLayer(layers[key], { opacity: 0.9, zIndex: zIndex }).addTo(overlayLayerGroup);
            } else {
                if (activeLayer) {
                    overlayLayerGroup.removeLayer(activeLayer);
                    activeLayer = null;
                }
            }
        };

        wrap.querySelector('input').addEventListener('change', (e) => toggleLayer(e.target.checked));

        // Auto-activate default layer
        if (isDefault) toggleLayer(true);

        container.appendChild(wrap);
    };

    createToggle('analytics', 'Depth Contours', '#ffffff', true); // Default On
    createToggle('depth', 'Bathymetry', '#0077b6', true); // Default On
    createToggle('water_mask', 'Water Extent', '#00FFFF');

    // Seasonal Layers
    createToggle('winter', 'Winter Spread', '#0891b2');
    createToggle('summer', 'Summer Spread', '#fb923c');
    createToggle('monsoon', 'Monsoon Spread', '#16a34a');

    document.getElementById('layerControlPanel').classList.remove('hidden');
}

// ... existing code ...

async function startScanning() {
    state.isScanning = true;
    const statusText = document.getElementById('scan-status');
    const overlay = document.getElementById('scanning-overlay'); // Keeping generic container but removing tech animation via CSS later if needed, or simplfying here

    // Simpler Loading State
    overlay.style.display = 'flex';
    // Remove the 'tech-ring' if you want a cleaner look, or just text
    statusText.innerText = "Analyzing Satellite Data...";

    try {
        const response = await fetch(`${API_BASE_URL}/api/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat: state.currentLat, lng: state.currentLng })
        });

        if (!response.ok) throw new Error("Analysis Service Failed");
        const data = await response.json();

        if (data.error) throw new Error(data.error);

        // Success
        state.currentArea = data.area;
        state.currentVol = data.volume;
        state.layers = data.layers;

        updateMetrics(data);
        updateCharts(data.volume, data.seasonal);
        updateLayerControl(data.layers);

        statusText.innerText = "Complete.";
        showToast("Analysis Complete.", "success");

    } catch (err) {
        console.error(err);
        const errMsg = err.message || "Unknown Error";
        showToast("Analysis Failed: " + errMsg, "error");
        statusText.innerText = "Error.";
        statusText.classList.add('text-red-500');
    } finally {
        setTimeout(() => {
            overlay.style.display = 'none';
            state.isScanning = false;
        }, 500);
    }
}

// --- Charts ---
function initCharts() {
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.05)';

    state.charts.trend = new Chart(document.getElementById('trendChart'), {
        type: 'line',
        data: {
            labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            datasets: [{
                label: 'Vol (MCM)',
                data: Array(12).fill(null),
                borderColor: '#06b6d4',
                backgroundColor: 'rgba(6, 182, 212, 0.1)',
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#06b6d4',
                pointBorderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { grid: { color: 'rgba(255,255,255,0.05)' } },
                x: { grid: { display: false } }
            }
        }
    });

    state.charts.seasonal = new Chart(document.getElementById('seasonalChart'), {
        type: 'bar',
        data: {
            labels: ['Summer', 'Monsoon', 'Winter'],
            datasets: [{
                label: 'Area (km²)',
                data: [0, 0, 0],
                backgroundColor: ['#f59e0b', '#22c55e', '#06b6d4'],
                borderRadius: 4,
                barThickness: 40
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { grid: { color: 'rgba(255,255,255,0.05)' } },
                x: { grid: { display: false } }
            }
        }
    });
}

function updateCharts(vol, seasonal) {
    // Trend Simulation
    const base = parseFloat(vol);
    const data = Array.from({ length: 12 }, () => base * (0.8 + Math.random() * 0.4));
    state.charts.trend.data.datasets[0].data = data;
    state.charts.trend.update();

    // Seasonal
    if (seasonal) {
        state.charts.seasonal.data.datasets[0].data = [seasonal.summer, seasonal.monsoon, seasonal.winter];
        state.charts.seasonal.update();
    }
}

// --- AI & Gemini ---
async function generateAIReport() {
    const btn = document.getElementById('aiBtn');
    const modal = document.getElementById('aiModal');
    const content = document.getElementById('aiContent');

    if (state.currentVol === 0) {
        showToast("Select a water body first!", "error");
        return;
    }

    btn.disabled = true;
    btn.innerHTML = `<span class="animate-spin mr-2">⟳</span> Connecting...`;

    const prompt = `
        Satellite Analysis [${state.currentLat.toFixed(4)}, ${state.currentLng.toFixed(4)}]:
        - Area: ${state.currentArea} km²
        - Volume: ${state.currentVol} MCM
        
        Provide a 3-point executive summary for water resource management.
        1. Significance of this volume.
        2. Recommendation for dry season.
        3. Potential agricultural application.
        Format as clear Markdown.
    `;

    try {
        const res = await fetch(apiURL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] })
        });

        const data = await res.json();
        const text = data.candidates?.[0]?.content?.parts?.[0]?.text || "AI Processing Error.";

        content.innerHTML = marked.parse(text);
        modal.classList.remove('hidden');
        modal.classList.add('flex'); // Show flex container

    } catch (e) {
        showToast("AI Error: " + e.message, "error");
    } finally {
        btn.disabled = false;
        btn.innerHTML = `✨ AI Analysis`;
    }
}

function closeAIModal() {
    const modal = document.getElementById('aiModal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

// --- Trigger AI Sim ---
function triggerAI() {
    state.map.flyTo([state.currentLat || 12.4244, state.currentLng || 76.5761], 14, { duration: 1.5 });
    setTimeout(() => {
        onMapClick({ latlng: { lat: (state.currentLat || 12.4244) + 0.005, lng: (state.currentLng || 76.5761) + 0.005 } });
    }, 1600);
}

// --- File Upload ---
function setupDropzones() {
    // Basic listener attachment if elements exist
    ['boundary', 'bathy'].forEach(type => {
        const input = document.getElementById(`${type}File`);
        if (input) {
            input.addEventListener('change', (e) => {
                if (e.target.files[0]) {
                    showToast(`Selected: ${e.target.files[0].name}`, 'success');
                }
            });
        }
    });
}
// Navigation
function navTo(id) {
    document.querySelectorAll('section').forEach(el => el.classList.add('hidden'));
    document.getElementById(id).classList.remove('hidden');

    document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('text-cyan-400', 'border-b-2', 'border-cyan-400'));
    document.getElementById(`nav-${id}`).classList.add('text-cyan-400', 'border-b-2', 'border-cyan-400');

    if (id === 'dashboard') setTimeout(() => state.map.invalidateSize(), 200);
}

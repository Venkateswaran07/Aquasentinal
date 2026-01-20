// Backend API Configuration
// Only edit the 'production' URL below after deploying your backend to Render/Railway.

const API_CONFIG = {
    // Development Environment (Localhost)
    development: 'http://127.0.0.1:5000',

    // Production Environment (Netlify -> Render)
    // REPLACE THIS URL with your actual Render Backend URL after deployment
    production: 'https://waterbodies-monitoring-system.onrender.com'
};

// Automatically select URL based on current hostname
const getApiUrl = () => {
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    return isLocal ? '' : API_CONFIG.production;
};

const API_BASE_URL = getApiUrl();
console.log("Using API Base URL:", API_BASE_URL);

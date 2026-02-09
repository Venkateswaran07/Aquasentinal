# Deployment Guide: AquaSense

This project has been restructured to support a split-deployment architecture, which is the industry standard for scalable web applications using specialized backend tools like Google Earth Engine (GEE).

## 1. Architecture Overview

- **Frontend (Netlify)**: Hosts `index.html`, CSS, and JS. Delivers the UI instantly to users globally.
- **Backend (Render/Railway)**: Hosts `server.py` (Flask). Processing GEE requests and serving the API.

## 2. Backend Deployment (Render.com)

The backend must be deployed first so you can get the API URL.

1. **Push your code** to GitHub.
2. **Create New Service on Render**:
    - Go to Render Dashboard -> **New +** -> **Web Service**.
    - Connect your GitHub repository.
3. **Configure Settings**:
    - **Runtime**: Python 3
    - **Build Command**: `pip install -r requirements.txt`
    - **Start Command**: `gunicorn server:app`
4. **Environment Variables** (Crucial!):
    - Add `PYTHON_VERSION` = `3.9.16` (or similar).
    - Add `GEE_CREDENTIALS_JSON`: Paste the **entire content** of your Google Cloud Service Account JSON key file here.
    - Add `GEMINI_API_KEY`: Your Google Gemini API Key (get it from aistudio.google.com).
5. **Deploy**: Click "Create Web Service".
6. **Copy URL**: Once live, copy your service URL (e.g., `https://aquasentinal-1.onrender.com`).

## 3. Frontend Deployment (Netlify)

1. **Update Config**:
    - Open `config.js` in your local project.
    - Paste your Render URL into the `production` field:

      ```javascript
      production: 'https://aquasentinal-1.onrender.com'
      ```

    - Commit and push this change to GitHub.
2. **Create New Site on Netlify**:
    - Go to Netlify -> **Add new site** -> **Import from Git**.
    - Select your repository.
3. **Configure Settings**:
    - **Build command**: (Leave empty)
    - **Publish directory**: `.` (or leave empty/root)
4. **Deploy**: Click "Deploy Site".

## 4. Verification

- Open your Netlify URL.
- Open the Developer Console (F12).
- Click on the map. You should see a network request to your Render URL.
- If you see "Analysis Complete", the connection is successful!

## Troubleshooting

- **CORS Errors**: Ensure `flask-cors` is installed (it is in `requirements.txt`) and `CORS(app)` is active in `server.py`.
- **GEE Auth Errors**: Check the Render logs. Ensure `GEE_CREDENTIALS_JSON` was pasted correctly.
- **Timeouts**: Google Earth Engine requests can be slow. Render's free tier spins down after inactivity (cold start takes ~50s). The first request might fail or be slow. Keep the backend warm or accept the delay.

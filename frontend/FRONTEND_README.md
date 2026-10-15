# InventoTrack frontend (React + Vite + Tailwind) - complete project

Folder layout
  package.json, vite.config.js, index.html, .env.example, .gitignore
  public/favicon.svg
  src/main.jsx          starts React, router and login state
  src/App.jsx           the list of pages (routes)
  src/api.js            ONE place that talks to the backend
  src/AuthContext.jsx   who is logged in
  src/components/       Layout (menu), RouteGuards, ui (buttons, cards), Charts
  src/pages/            one file per screen

Run it
  npm install
  copy .env.example .env      (PowerShell: Copy-Item .env.example .env)
  npm run dev

Build for deployment: npm run build  (output folder: dist)
Render Static Site: build "npm install && npm run build", publish "dist",
env VITE_API_URL=https://invento-track.onrender.com, rewrite /* -> /index.html.
Add the site address to the backend CORS_ORIGINS.

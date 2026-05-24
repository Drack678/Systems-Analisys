import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx?v=tm";

const rootEl = document.getElementById("root");

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Oculta la pantalla de carga una vez React monta
if (typeof window.__hideSplash === "function") {
  window.__hideSplash();
}

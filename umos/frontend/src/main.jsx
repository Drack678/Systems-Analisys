import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./styles/index.css";

const rootEl = document.getElementById("root");

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

if (typeof window.__hideSplash === "function") {
  window.__hideSplash();
}

import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

// Styles
import "./styles/variables.css";
import "./styles/base.css";
import "./styles/layouts.css";
import "./styles/pages.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

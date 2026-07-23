import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import "./styles/tokens.css";
import "./styles/utilities.css";
import "./styles/app.css";
import "./styles/scrollbars.css";
import { App } from "./App";

const container = document.getElementById("root");
if (!container) throw new Error("root element #root not found in index.html");

// The Router lives here rather than in App so tests can mount App at an arbitrary URL with
// a MemoryRouter. Deep links need the host to serve index.html for unknown paths — Vite's
// dev server and `vite preview` already do; see README for production hosting.
createRoot(container).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);

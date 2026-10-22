import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, HashRouter } from "react-router-dom";

import App from "./App";
import { AuthProvider } from "./lib/auth";
import "./styles.css";

const demo = import.meta.env.VITE_DEMO === "1";

async function start() {
  if (demo) {
    // Static preview build: no server, so the API is answered from memory.
    const { installDemoApi } = await import("./demo/api");
    installDemoApi();
  }
  const Router = demo ? HashRouter : BrowserRouter;

  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <Router>
        <AuthProvider>
          <App />
        </AuthProvider>
      </Router>
    </StrictMode>,
  );
}

void start();

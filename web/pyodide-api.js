"use strict";

// GitHub Pages has no server. This script starts the real control plane in
// Pyodide and answers the dashboard's fetch("/api/...") calls from
// web/bridge.py, so static/app.js runs unchanged. Other requests pass through.
(() => {
  const realFetch = window.fetch.bind(window);

  function setEnvironment(text) {
    const label = document.querySelector(".environment strong");
    if (label) label.textContent = text;
  }

  const ready = (async () => {
    const pyodide = await loadPyodide();
    await pyodide.loadPackage("pydantic");
    const manifest = await (await realFetch("py/manifest.json")).json();
    for (const path of manifest) {
      const source = await (await realFetch("py/" + path)).text();
      const full = "/home/pyodide/" + path;
      pyodide.FS.mkdirTree(full.split("/").slice(0, -1).join("/"));
      pyodide.FS.writeFile(full, source);
    }
    const bridge = pyodide.pyimport("bridge");
    setEnvironment("Python ready");
    return bridge;
  })();

  ready.catch((err) => {
    console.error(err);
    setEnvironment("Python failed to load");
  });

  window.fetch = async (input, init = {}) => {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    const at = url.pathname.indexOf("/api/");
    if (at < 0) return realFetch(input, init);
    const bridge = await ready;
    const method = init.method || (typeof input === "string" ? "GET" : input.method);
    const reply = JSON.parse(bridge.handle(method, url.pathname.slice(at) + url.search));
    return new Response(JSON.stringify(reply.body), {
      status: reply.status,
      headers: { "Content-Type": "application/json" },
    });
  };

  document.addEventListener("DOMContentLoaded", () => setEnvironment("Loading Python…"));
})();

const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://localhost:8000"
  : "https://price-tracker-5jbv.onrender.com";

const state = { selected: null };
const $ = (selector) => document.querySelector(selector);

function setMessage(text, error = false) {
  const message = $("#search-message");
  message.textContent = text;
  message.className = `message${error ? " error" : ""}`;
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, { headers: { "Content-Type": "application/json" }, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function formatTime(value) {
  return value ? new Date(value).toLocaleString() : "-";
}

function productCard(product, actionLabel = "View") {
  const card = document.createElement("article");
  card.className = "product-card";
  card.innerHTML = `<div><strong>${escapeHtml(product.name)}</strong><span>${product.last_known_price ? `₹${product.last_known_price}` : "No successful price yet"}</span></div><button class="button small" type="button">${actionLabel}</button>`;
  return card;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>\"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[character]);
}

async function search(event) {
  event.preventDefault();
  const query = $("#search-input").value.trim();
  if (!query) return;
  setMessage("Searching the store...");
  $("#search-results").replaceChildren();
  try {
    const data = await api(`/api/products/search?q=${encodeURIComponent(query)}`);
    if (!data.results.length) return setMessage("No matching products found.");
    setMessage(`${data.results.length} product${data.results.length === 1 ? "" : "s"} found.`);
    data.results.forEach((product) => {
      const card = productCard({ name: product.name });
      card.querySelector("button").textContent = "Track product";
      card.querySelector("button").addEventListener("click", () => track(product));
      $("#search-results").append(card);
    });
  } catch (error) { setMessage(error.message, true); }
}

async function track(product) {
  setMessage(`Tracking ${product.name} and taking the first reading...`);
  try {
    await api("/api/products/track", { method: "POST", body: JSON.stringify({ name: product.name, url: product.store_product_url }) });
    setMessage(`${product.name} is now tracked.`);
    await loadTracked();
  } catch (error) { setMessage(error.message, true); }
}

async function loadTracked() {
  try {
    const data = await api("/api/products");
    $("#tracked-count").textContent = data.results.length;
    const list = $("#tracked-products");
    list.replaceChildren();
    if (!data.results.length) { list.innerHTML = '<p class="muted">No products tracked yet.</p>'; return; }
    data.results.forEach((product) => {
      const card = productCard(product);
      card.addEventListener("click", () => selectProduct(product));
      list.append(card);
    });
    if (state.selected) {
      const refreshed = data.results.find((product) => product.id === state.selected.id);
      if (refreshed) selectProduct(refreshed);
    }
  } catch (error) { $("#tracked-products").innerHTML = `<p class="message error">${escapeHtml(error.message)}</p>`; }
}

async function selectProduct(product) {
  state.selected = product;
  $("#details-panel").hidden = false;
  $("#selected-name").textContent = product.name;
  $("#selected-url").textContent = product.store_product_url;
  $("#selected-price").textContent = product.last_known_price ? `₹${product.last_known_price}` : "-";
  $("#selected-stock").textContent = product.last_known_stock || "unknown";
  try {
    const [history, logs] = await Promise.all([api(`/api/products/${product.id}/history`), api(`/api/products/${product.id}/logs`)]);
    $("#history-count").textContent = history.results.length;
    $("#log-count").textContent = logs.results.length;
    $("#history-body").innerHTML = history.results.length ? history.results.map((row) => `<tr><td>${formatTime(row.scraped_at)}</td><td>₹${escapeHtml(row.price)}</td><td>${escapeHtml(row.stock_status)}</td></tr>`).join("") : '<tr><td colspan="3" class="muted">No successful readings yet.</td></tr>';
    $("#logs-body").innerHTML = logs.results.length ? logs.results.map((row) => `<tr><td>${formatTime(row.created_at)}</td><td><span class="status ${row.status}">${row.status}</span></td><td>${row.attempt_number}</td><td>${escapeHtml(row.failure_reason || "-")}</td><td>${row.duration_ms ? `${row.duration_ms} ms` : "-"}</td></tr>`).join("") : '<tr><td colspan="5" class="muted">No scrape attempts yet.</td></tr>';
  } catch (error) { setMessage(error.message, true); }
}

document.addEventListener("DOMContentLoaded", () => {
  $("#search-form").addEventListener("submit", search);
  $("#refresh-button").addEventListener("click", loadTracked);
  loadTracked();
});

"use strict";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const state = {
  front: null, // File
  back: null,  // File
  extracted: null, // { front_image, back_image, extracted }
  editingPk: null,
};

const FIELDS = [
  "player", "year", "brand", "set_name", "card_number",
  "variation", "team", "sport", "is_rookie", "condition", "notes",
];

// ---------- Navigation ----------
function showView(name) {
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === name));
  $("#view-inventory").classList.toggle("hidden", name !== "inventory");
  $("#view-add").classList.toggle("hidden", name !== "add");
  if (name === "inventory") loadInventory();
  if (name === "add") resetAdd();
}

$$(".tab").forEach((t) => t.addEventListener("click", () => showView(t.dataset.view)));

// ---------- Dashboard ----------
async function loadStats() {
  const r = await fetch("/api/dashboard");
  const d = await r.json();
  const money = (n) => "$" + Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  $("#stats").innerHTML = `
    <div class="stat"><div class="num">${d.total_cards}</div><div class="label">Cards</div></div>
    <div class="stat"><div class="num">${d.by_status.in_stock + d.by_status.listed}</div><div class="label">In stock</div></div>
    <div class="stat"><div class="num">${money(d.cost_basis)}</div><div class="label">Cost basis</div></div>
    <div class="stat good"><div class="num">${money(d.profit)}</div><div class="label">Profit</div></div>
  `;
}

// ---------- Inventory ----------
async function loadInventory() {
  const q = $("#search").value.trim();
  const status = $("#filter-status").value;
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (status) params.set("status", status);
  const r = await fetch("/api/cards?" + params.toString());
  const cards = await r.json();

  const list = $("#card-list");
  $("#empty-inventory").classList.toggle("hidden", cards.length > 0);
  list.innerHTML = cards.map(cardTile).join("");
  $$("#card-list .card").forEach((el) =>
    el.addEventListener("click", () => openEdit(Number(el.dataset.pk)))
  );
  loadStats();
}

function cardTile(c) {
  const thumb = c.front_image
    ? `style="background-image:url('/images/${c.front_image}')"`
    : "";
  const sub = [c.year, c.brand, c.set_name].filter(Boolean).join(" ");
  return `
    <div class="card" data-pk="${c.id}">
      <div class="thumb" ${thumb}>${c.front_image ? "" : "no image"}</div>
      <div class="info">
        <div class="player">${esc(c.player) || "Unknown player"}</div>
        <div class="meta">${esc(sub) || "&nbsp;"}</div>
        <div class="row">
          <span class="invid">${esc(c.card_id)}</span>
          <span class="badge ${c.status}">${c.status.replace("_", " ")}</span>
        </div>
      </div>
    </div>`;
}

$("#search").addEventListener("input", debounce(loadInventory, 250));
$("#filter-status").addEventListener("change", loadInventory);

// ---------- Add flow ----------
function resetAdd() {
  state.front = state.back = state.extracted = null;
  $("#front-input").value = "";
  $("#back-input").value = "";
  $("#front-shot").style.backgroundImage = "";
  $("#back-shot").style.backgroundImage = "";
  $("#front-shot").classList.remove("filled");
  $("#back-shot").classList.remove("filled");
  $("#scan-btn").disabled = true;
  $("#scan-msg").textContent = "";
  $("#capture-step").classList.remove("hidden");
  $("#review-form").classList.add("hidden");
  $("#review-form").reset();
}

function bindShot(inputId, shotId, key) {
  $(inputId).addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    state[key] = file;
    const url = URL.createObjectURL(file);
    $(shotId).style.backgroundImage = `url('${url}')`;
    $(shotId).classList.add("filled");
    $("#scan-btn").disabled = !state.front;
  });
}
bindShot("#front-input", "#front-shot", "front");
bindShot("#back-input", "#back-shot", "back");

$("#scan-btn").addEventListener("click", async () => {
  if (!state.front) return;
  const btn = $("#scan-btn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Reading…';
  $("#scan-msg").textContent = "";
  try {
    const fd = new FormData();
    fd.append("front", state.front);
    if (state.back) fd.append("back", state.back);
    const r = await fetch("/api/cards/extract", { method: "POST", body: fd });
    if (!r.ok) throw new Error("Extract failed (" + r.status + ")");
    const data = await r.json();
    state.extracted = data;
    fillReview(data);
    $("#capture-step").classList.add("hidden");
    $("#review-form").classList.remove("hidden");
  } catch (err) {
    $("#scan-msg").textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Read card with Claude";
  }
});

function fillReview(data) {
  const f = $("#review-form");
  FIELDS.forEach((k) => {
    if (f.elements[k]) f.elements[k].value = data.extracted[k] || "";
  });
  $("#vision-note").textContent = data.vision_used
    ? "✨ " + data.message
    : "✍️ " + data.message;
}

$("#cancel-add").addEventListener("click", () => showView("inventory"));

$("#review-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const payload = { front_image: state.extracted.front_image, back_image: state.extracted.back_image };
  FIELDS.forEach((k) => { if (f.elements[k]) payload[k] = f.elements[k].value; });
  payload.status = f.elements["status"].value;
  payload.purchase_price = parseFloatOrNull(f.elements["purchase_price"].value);

  const r = await fetch("/api/cards", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (r.ok) {
    showView("inventory");
  } else {
    alert("Could not save card.");
  }
});

// ---------- Edit modal ----------
async function openEdit(pk) {
  const r = await fetch("/api/cards/" + pk);
  const c = await r.json();
  state.editingPk = pk;
  const f = $("#edit-form");
  ["player", "year", "brand", "set_name", "card_number", "variation", "team", "sport", "condition", "notes"].forEach((k) => {
    if (f.elements[k]) f.elements[k].value = c[k] || "";
  });
  f.elements["status"].value = c.status;
  f.elements["purchase_price"].value = c.purchase_price ?? "";
  f.elements["sale_price"].value = c.sale_price ?? "";
  $("#edit-title").textContent = `${c.card_id} — ${c.player || "card"}`;
  $("#edit-modal").classList.remove("hidden");
}

$("#close-edit").addEventListener("click", () => $("#edit-modal").classList.add("hidden"));

$("#edit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const payload = {};
  ["player", "year", "brand", "set_name", "card_number", "variation", "team", "sport", "condition", "notes", "status"].forEach((k) => {
    if (f.elements[k]) payload[k] = f.elements[k].value;
  });
  payload.purchase_price = parseFloatOrNull(f.elements["purchase_price"].value);
  payload.sale_price = parseFloatOrNull(f.elements["sale_price"].value);
  const r = await fetch("/api/cards/" + state.editingPk, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (r.ok) {
    $("#edit-modal").classList.add("hidden");
    loadInventory();
  } else {
    alert("Could not save changes.");
  }
});

$("#delete-card").addEventListener("click", async () => {
  if (!confirm("Delete this card from inventory?")) return;
  await fetch("/api/cards/" + state.editingPk, { method: "DELETE" });
  $("#edit-modal").classList.add("hidden");
  loadInventory();
});

// ---------- Helpers ----------
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}
function parseFloatOrNull(v) {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : null;
}
function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// ---------- Init ----------
loadInventory();

"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const state = { front: null, back: null, uploaded: null, editingPk: null, checklistId: null };

const FIELDS = ["player","year","brand","set_name","card_number","variation","team","sport","is_rookie","condition","notes"];
const money = (n) => "$" + Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// ---------- Navigation ----------
function showView(name) {
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === name));
  ["inventory","add","sales","checklists"].forEach((v) =>
    $("#view-" + v).classList.toggle("hidden", v !== name));
  if (name === "inventory") loadInventory();
  if (name === "add") resetAdd();
  if (name === "sales") loadSales();
  if (name === "checklists") loadChecklists();
}
$$(".tab").forEach((t) => t.addEventListener("click", () => showView(t.dataset.view)));

// ---------- Dashboard / Inventory ----------
async function loadStats() {
  const d = await (await fetch("/api/dashboard")).json();
  $("#stats").innerHTML = `
    <div class="stat"><div class="num">${d.total_cards}</div><div class="label">Cards</div></div>
    <div class="stat"><div class="num">${d.by_status.in_stock + d.by_status.listed}</div><div class="label">In stock</div></div>
    <div class="stat"><div class="num">${money(d.inventory_cost)}</div><div class="label">Inventory cost</div></div>
    <div class="stat ${d.net_profit >= 0 ? "good" : "bad"}"><div class="num">${money(d.net_profit)}</div><div class="label">Net profit</div></div>`;
}

async function loadInventory() {
  const q = $("#search").value.trim();
  const status = $("#filter-status").value;
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (status) params.set("status", status);
  const cards = await (await fetch("/api/cards?" + params)).json();
  $("#empty-inventory").classList.toggle("hidden", cards.length > 0);
  const list = $("#card-list");
  list.innerHTML = cards.map(cardTile).join("");
  $$("#card-list .card").forEach((el) => el.addEventListener("click", () => openEdit(Number(el.dataset.pk))));
  loadStats();
}

function cardTile(c) {
  const thumb = c.front_image ? `style="background-image:url('/images/${c.front_image}')"` : "";
  const sub = [c.year, c.brand, c.set_name].filter(Boolean).join(" ");
  return `<div class="card" data-pk="${c.id}">
    <div class="thumb" ${thumb}>${c.front_image ? "" : "no image"}</div>
    <div class="info">
      <div class="player">${esc(c.player) || "Unknown player"}</div>
      <div class="meta">${esc(sub) || "&nbsp;"}</div>
      <div class="row"><span class="invid">${esc(c.card_id)}</span><span class="badge ${c.status}">${c.status.replace("_"," ")}</span></div>
    </div></div>`;
}

$("#search").addEventListener("input", debounce(loadInventory, 250));
$("#filter-status").addEventListener("change", loadInventory);

// ---------- Add flow (free) ----------
function resetAdd() {
  closeCamera();
  state.front = state.back = state.uploaded = null;
  $("#front-input").value = ""; $("#back-input").value = "";
  ["#front-shot","#back-shot"].forEach((s) => { $(s).style.backgroundImage = ""; $(s).classList.remove("filled"); });
  $("#scan-btn").disabled = true;
  $("#scan-btn").textContent = "Scan & continue";
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
    $(shotId).style.backgroundImage = `url('${URL.createObjectURL(file)}')`;
    $(shotId).classList.add("filled");
    $("#scan-btn").disabled = !state.front;
  });
}
bindShot("#front-input", "#front-shot", "front");
bindShot("#back-input", "#back-shot", "back");

function applyShot(key, file) {
  state[key] = file;
  const shot = key === "front" ? "#front-shot" : "#back-shot";
  $(shot).style.backgroundImage = `url('${URL.createObjectURL(file)}')`;
  $(shot).classList.add("filled");
  $("#scan-btn").disabled = !state.front;
}

// ---------- Webcam capture (laptop/desktop; works over localhost) ----------
const cam = { target: "front", stream: null };

async function openCamera() {
  setCamTarget(state.front ? "back" : "front");
  $("#cam-msg").textContent = "Hold the card up to your camera and fill the frame.";
  $("#camera-modal").classList.remove("hidden");
  try {
    cam.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
    $("#cam-video").srcObject = cam.stream;
  } catch (err) {
    const name = err && err.name ? err.name : "error";
    $("#cam-msg").textContent =
      "Couldn't open the camera (" + name + "). Close this and tap a box to choose a saved photo, or use your phone.";
  }
}

function setCamTarget(t) {
  cam.target = t;
  $("#cam-label").textContent = "📷 Capture " + t.toUpperCase();
  $("#cam-capture").textContent = "📸 Capture " + t;
}

function captureShot() {
  const v = $("#cam-video");
  if (!v.videoWidth) { $("#cam-msg").textContent = "Camera still starting — try again in a second."; return; }
  const canvas = document.createElement("canvas");
  canvas.width = v.videoWidth;
  canvas.height = v.videoHeight;
  canvas.getContext("2d").drawImage(v, 0, 0);
  canvas.toBlob((blob) => {
    if (!blob) return;
    applyShot(cam.target, new File([blob], cam.target + ".jpg", { type: "image/jpeg" }));
    if (cam.target === "front") {
      setCamTarget("back");
      $("#cam-msg").textContent = "Front captured ✓ — now show the back, or tap Done.";
    } else {
      $("#cam-msg").textContent = "Back captured ✓ — tap Done.";
    }
  }, "image/jpeg", 0.9);
}

function closeCamera() {
  if (cam.stream) { cam.stream.getTracks().forEach((t) => t.stop()); cam.stream = null; }
  $("#camera-modal").classList.add("hidden");
}

$("#camera-btn").addEventListener("click", openCamera);
$("#cam-capture").addEventListener("click", captureShot);
$("#cam-done").addEventListener("click", closeCamera);
$("#cam-close").addEventListener("click", closeCamera);

$("#scan-btn").addEventListener("click", async () => {
  if (!state.front) return;
  const btn = $("#scan-btn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Saving photos…';
  $("#scan-msg").textContent = "";
  try {
    // 1) Store the photos (free, no AI)
    const fd = new FormData();
    fd.append("front", state.front);
    if (state.back) fd.append("back", state.back);
    const up = await fetch("/api/cards/upload", { method: "POST", body: fd });
    if (!up.ok) throw new Error("Upload failed (" + up.status + ")");
    state.uploaded = await up.json();

    // 2) Best-effort on-device text scan (free). Skips silently if unavailable.
    let note = "✍️ Type the card details below.";
    const guess = await tryOcr(btn);
    if (guess) {
      const f = $("#review-form");
      Object.entries(guess.fields).forEach(([k, v]) => { if (f.elements[k] && v) f.elements[k].value = v; });
      note = "🔎 Scanned the text on your device (free). Please double-check the details.";
    }
    $("#vision-note").textContent = note;
    $("#capture-step").classList.add("hidden");
    $("#review-form").classList.remove("hidden");
  } catch (err) {
    $("#scan-msg").textContent = err.message;
    btn.disabled = false;
    btn.textContent = "Scan & continue";
  }
});

async function tryOcr(btn) {
  if (typeof Tesseract === "undefined" || !state.front) return null;
  try {
    btn.innerHTML = '<span class="spinner"></span> Reading card (free)…';
    const { data } = await Tesseract.recognize(state.front, "eng");
    return parseOcr(data.text || "");
  } catch {
    return null; // offline or failed → fall back to manual
  }
}

function parseOcr(text) {
  const fields = {};
  const yr = text.match(/\b(19|20)\d{2}\b/);
  if (yr) fields.year = yr[0];
  const num = text.match(/(?:#|no\.?\s*)\s*([A-Z]{0,3}-?\d{1,4})/i);
  if (num) fields.card_number = num[1];
  // Player guess: a 2-3 word, mostly-letters line near the top
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const candidate = lines.find((l) => {
    const words = l.split(/\s+/);
    return words.length >= 2 && words.length <= 3 && /^[A-Za-z.'\- ]{5,28}$/.test(l);
  });
  if (candidate) fields.player = candidate.replace(/\s+/g, " ").trim();
  fields.notes = "Scanned text:\n" + text.replace(/\n{2,}/g, "\n").trim().slice(0, 400);
  return { fields };
}

$("#cancel-add").addEventListener("click", () => showView("inventory"));

$("#review-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const payload = { front_image: state.uploaded.front_image, back_image: state.uploaded.back_image };
  FIELDS.forEach((k) => { if (f.elements[k]) payload[k] = f.elements[k].value; });
  payload.status = f.elements["status"].value;
  payload.purchase_price = numOrNull(f.elements["purchase_price"].value);
  payload.purchase_source = f.elements["purchase_source"].value;
  payload.purchase_date = f.elements["purchase_date"].value;
  const r = await fetch("/api/cards", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (r.ok) showView("inventory"); else alert("Could not save card.");
});

// ---------- Edit modal ----------
async function openEdit(pk) {
  const c = await (await fetch("/api/cards/" + pk)).json();
  state.editingPk = pk;
  const f = $("#edit-form");
  ["player","year","brand","set_name","card_number","variation","team","sport","condition","notes","purchase_source","sale_platform","sale_date"].forEach((k) => { if (f.elements[k]) f.elements[k].value = c[k] || ""; });
  f.elements["status"].value = c.status;
  f.elements["purchase_price"].value = c.purchase_price ?? "";
  f.elements["sale_price"].value = c.sale_price ?? "";
  f.elements["sale_fees"].value = c.sale_fees ?? "";
  f.elements["sale_shipping"].value = c.sale_shipping ?? "";
  $("#edit-title").textContent = `${c.card_id} — ${c.player || "card"}`;
  updateProfitLine();
  $("#edit-modal").classList.remove("hidden");
}

function updateProfitLine() {
  const f = $("#edit-form");
  const sale = numOrNull(f.elements["sale_price"].value);
  if (sale === null) { $("#edit-profit").textContent = ""; return; }
  const cost = numOrNull(f.elements["purchase_price"].value) || 0;
  const fees = numOrNull(f.elements["sale_fees"].value) || 0;
  const ship = numOrNull(f.elements["sale_shipping"].value) || 0;
  const profit = sale - cost - fees - ship;
  $("#edit-profit").innerHTML = `Net profit: <b class="${profit >= 0 ? "pos" : "neg"}">${money(profit)}</b>`;
}
["purchase_price","sale_price","sale_fees","sale_shipping"].forEach((n) =>
  $("#edit-form").elements[n].addEventListener("input", updateProfitLine));

$("#close-edit").addEventListener("click", () => $("#edit-modal").classList.add("hidden"));

$("#edit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const payload = {};
  ["player","year","brand","set_name","card_number","variation","team","sport","condition","notes","status","purchase_source","sale_platform","sale_date"].forEach((k) => { if (f.elements[k]) payload[k] = f.elements[k].value; });
  ["purchase_price","sale_price","sale_fees","sale_shipping"].forEach((k) => { payload[k] = numOrNull(f.elements[k].value); });
  const r = await fetch("/api/cards/" + state.editingPk, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (r.ok) { $("#edit-modal").classList.add("hidden"); loadInventory(); } else alert("Could not save changes.");
});

$("#delete-card").addEventListener("click", async () => {
  if (!confirm("Delete this card from inventory?")) return;
  await fetch("/api/cards/" + state.editingPk, { method: "DELETE" });
  $("#edit-modal").classList.add("hidden");
  loadInventory();
});

// ---------- Sales view ----------
async function loadSales() {
  const d = await (await fetch("/api/dashboard")).json();
  $("#sales-stats").innerHTML = `
    <div class="stat"><div class="num">${money(d.revenue)}</div><div class="label">Revenue</div></div>
    <div class="stat"><div class="num">${money(d.cost_of_sold)}</div><div class="label">Cost of cards sold</div></div>
    <div class="stat"><div class="num">${money(d.fees)}</div><div class="label">Fees + shipping</div></div>
    <div class="stat ${d.net_profit >= 0 ? "good" : "bad"}"><div class="num">${money(d.net_profit)}</div><div class="label">Net profit · ${d.roi}% ROI</div></div>`;
  const sold = await (await fetch("/api/cards?status=sold")).json();
  $("#empty-sales").classList.toggle("hidden", sold.length > 0);
  $("#sales-list").innerHTML = sold.map((c) => {
    const p = c.net_profit ?? 0;
    return `<div class="sale-row" data-pk="${c.id}">
      <div class="sale-thumb" style="background-image:url('/images/${c.front_image || ""}')"></div>
      <div class="sale-main">
        <div class="player">${esc(c.player) || c.card_id}</div>
        <div class="meta">${esc([c.year,c.brand,c.set_name].filter(Boolean).join(" "))} · sold ${esc(c.sale_date) || "—"} ${c.sale_platform ? "on " + esc(c.sale_platform) : ""}</div>
      </div>
      <div class="sale-fig"><div>${money(c.sale_price)}</div><div class="profit ${p>=0?"pos":"neg"}">${p>=0?"+":""}${money(p)}</div></div>
    </div>`;
  }).join("");
  $$("#sales-list .sale-row").forEach((el) => el.addEventListener("click", () => openEdit(Number(el.dataset.pk))));
}

// ---------- Checklists ----------
async function loadChecklists() {
  const sets = await (await fetch("/api/checklists")).json();
  $("#empty-sets").classList.toggle("hidden", sets.length > 0);
  $("#set-list").innerHTML = sets.map((s) => `
    <div class="set-card" data-id="${s.id}">
      <div class="set-head"><b>${esc([s.year,s.brand,s.name].filter(Boolean).join(" "))}</b><span>${s.owned_items}/${s.total_items}</span></div>
      <div class="bar"><div class="bar-fill" style="width:${s.pct_complete}%"></div></div>
      <div class="set-sub">${s.pct_complete}% complete${s.sport ? " · " + esc(s.sport) : ""}</div>
    </div>`).join("");
  $$("#set-list .set-card").forEach((el) => el.addEventListener("click", () => openChecklist(Number(el.dataset.id))));
}

$("#new-set-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const payload = { name: f.elements["name"].value, year: f.elements["year"].value, brand: f.elements["brand"].value, sport: f.elements["sport"].value };
  const r = await fetch("/api/checklists", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (r.ok) { f.reset(); loadChecklists(); } else alert("Could not create checklist.");
});

async function openChecklist(id) {
  state.checklistId = id;
  const d = await (await fetch("/api/checklists/" + id)).json();
  const s = d.set;
  $("#checklist-title").textContent = [s.year, s.brand, s.name].filter(Boolean).join(" ") || "Checklist";
  $("#checklist-progress").innerHTML = `<div class="bar"><div class="bar-fill" style="width:${s.pct_complete}%"></div></div><div class="set-sub">${s.owned_items}/${s.total_items} owned · ${s.pct_complete}% complete</div>`;
  renderItems(d.items);
  $("#checklist-modal").classList.remove("hidden");
}

function renderItems(items) {
  $("#checklist-items").innerHTML = items.map((i) => `
    <label class="cl-item ${i.owned ? "owned" : ""}" data-id="${i.id}">
      <input type="checkbox" ${i.owned ? "checked" : ""} />
      <span class="cl-num">${esc(i.card_number) || "—"}</span>
      <span class="cl-player">${esc(i.player) || "(no name)"}</span>
      <span class="cl-var">${esc(i.variation || "")}</span>
      <button type="button" class="cl-del" title="Remove">✕</button>
    </label>`).join("");
  $$("#checklist-items .cl-item").forEach((el) => {
    const id = Number(el.dataset.id);
    el.querySelector("input").addEventListener("change", (e) => toggleItem(id, e.target.checked, el));
    el.querySelector(".cl-del").addEventListener("click", (e) => { e.preventDefault(); deleteItem(id); });
  });
}

async function toggleItem(id, owned, el) {
  el.classList.toggle("owned", owned);
  await fetch("/api/checklists/items/" + id, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ owned }) });
  refreshChecklistProgress();
}
async function deleteItem(id) {
  await fetch("/api/checklists/items/" + id, { method: "DELETE" });
  openChecklist(state.checklistId);
}
async function refreshChecklistProgress() {
  const d = await (await fetch("/api/checklists/" + state.checklistId)).json();
  const s = d.set;
  $("#checklist-progress").innerHTML = `<div class="bar"><div class="bar-fill" style="width:${s.pct_complete}%"></div></div><div class="set-sub">${s.owned_items}/${s.total_items} owned · ${s.pct_complete}% complete</div>`;
}

$("#add-item-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  await fetch(`/api/checklists/${state.checklistId}/items`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ card_number: f.elements["card_number"].value, player: f.elements["player"].value, variation: f.elements["variation"].value }) });
  f.reset();
  openChecklist(state.checklistId);
});

$("#import-input").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch(`/api/checklists/${state.checklistId}/import`, { method: "POST", body: fd });
  const res = await r.json();
  e.target.value = "";
  if (r.ok) { alert(`Imported ${res.imported} cards.`); openChecklist(state.checklistId); }
  else alert("Import failed.");
});

$("#delete-set").addEventListener("click", async () => {
  if (!confirm("Delete this whole checklist?")) return;
  await fetch("/api/checklists/" + state.checklistId, { method: "DELETE" });
  $("#checklist-modal").classList.add("hidden");
  loadChecklists();
});
$("#close-checklist").addEventListener("click", () => $("#checklist-modal").classList.add("hidden"));

// ---------- Helpers ----------
function esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c])); }
function numOrNull(v) { const n = parseFloat(v); return Number.isFinite(n) ? n : null; }
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

loadInventory();

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

    // 2) Best-effort on-device text scan (free). Reads the BACK if available
    //    (card backs scan much better than glossy fronts).
    const f = $("#review-form");
    const r = await tryOcr(btn);
    let note;
    if (r.status === "ok") {
      Object.entries(r.fields).forEach(([k, v]) => { if (f.elements[k] && v) f.elements[k].value = v; });
      note = r.filled > 0
        ? "🔎 Read the card on your device (free) and filled what it could. Please double-check every field."
        : "🔎 Couldn't make out much automatically (foil/fonts are hard for a free scanner). Photos saved — just type the details. Tip: a clear shot of the BACK reads best.";
    } else if (r.status === "unavailable") {
      note = "⚠️ The free scanner didn't load (it needs a small one-time internet download). Photos saved — type the details, or retry on stronger Wi-Fi.";
    } else {
      note = "✍️ Photos saved — type the card details below.";
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
  if (typeof Tesseract === "undefined") return { status: "unavailable" };
  const img = state.back || state.front; // backs read much better than glossy fronts
  if (!img) return { status: "error" };
  try {
    const { data } = await Tesseract.recognize(img, "eng", {
      logger: (m) => {
        if (m.status === "recognizing text")
          btn.innerHTML = '<span class="spinner"></span> Reading card… ' + Math.round((m.progress || 0) * 100) + "%";
      },
    });
    const fields = parseOcr(data.text || "");
    const filled = ["player","year","brand","set_name","card_number","team","sport"].filter((k) => fields[k]).length;
    return { status: "ok", fields, filled };
  } catch {
    return { status: "error" };
  }
}

const BRANDS = ["Topps","Panini","Bowman","Upper Deck","Fleer","Donruss","Score","Leaf","Pro Set","O-Pee-Chee"];
const SETS = ["Chrome","Prizm","Select","Mosaic","Optic","Stadium Club","Heritage","Finest","Allen & Ginter","Gallery","Contenders","Chronicles","Sapphire","Gypsy Queen","Big League","Inception","Obsidian","National Treasures","Flawless","Immaculate","Hoops","Revolution","Update","Archives","Donruss"];
const TEAMS = {
  Baseball: ["Diamondbacks","Braves","Orioles","Red Sox","Cubs","White Sox","Reds","Guardians","Rockies","Tigers","Astros","Royals","Angels","Dodgers","Marlins","Brewers","Twins","Mets","Yankees","Athletics","Phillies","Pirates","Padres","Giants","Mariners","Cardinals","Rays","Rangers","Blue Jays","Nationals"],
  Basketball: ["Hawks","Celtics","Nets","Hornets","Bulls","Cavaliers","Mavericks","Nuggets","Pistons","Warriors","Rockets","Pacers","Clippers","Lakers","Grizzlies","Heat","Bucks","Timberwolves","Pelicans","Knicks","Thunder","Magic","76ers","Suns","Trail Blazers","Kings","Spurs","Raptors","Jazz","Wizards"],
  Football: ["Cardinals","Falcons","Ravens","Bills","Panthers","Bears","Bengals","Browns","Cowboys","Broncos","Lions","Packers","Texans","Colts","Jaguars","Chiefs","Raiders","Chargers","Rams","Dolphins","Vikings","Patriots","Saints","Giants","Jets","Eagles","Steelers","49ers","Seahawks","Buccaneers","Commanders","Titans"],
  Hockey: ["Ducks","Bruins","Sabres","Flames","Hurricanes","Blackhawks","Avalanche","Blue Jackets","Stars","Red Wings","Oilers","Panthers","Wild","Canadiens","Predators","Devils","Islanders","Senators","Flyers","Penguins","Sharks","Kraken","Blues","Lightning","Maple Leafs","Canucks","Golden Knights","Capitals","Coyotes"],
};
const STAT_HINTS = {
  Baseball: ["HOME RUN"," HR "," RBI "," AVG "," ERA ","BATTING","PITCHER","INNINGS","STOLEN"],
  Basketball: ["REBOUND","ASSIST","POINTS PER"," PPG "," NBA ","FIELD GOAL","FREE THROW"],
  Football: ["YARDS","TOUCHDOWN","RUSHING","RECEIVING","PASSING","QUARTERBACK"," NFL ","RECEPTION"],
  Hockey: ["GOALS"," NHL ","PENALTY","POWER PLAY","SHUTOUT","FACEOFF"],
};
const NAME_BANNED = [...BRANDS, ...SETS, "ROOKIE","CARD","OFFICIAL","COMPANY","BASEBALL","BASKETBALL","FOOTBALL","HOCKEY","STATS","CAREER","LEAGUE","DRAFT","MLB","NBA","NFL","NHL","ALL STAR","WORLD SERIES"].map((w) => w.toUpperCase());

function titleCase(s) { return s.toLowerCase().replace(/\b[a-z]/g, (c) => c.toUpperCase()); }

function parseOcr(text) {
  const fields = {};
  const upper = " " + text.toUpperCase().replace(/[\n\r]+/g, " ") + " ";
  const lines = text.split("\n").map((l) => l.replace(/\s+/g, " ").trim()).filter(Boolean);

  // Year — prefer a season (2023-24); else any 19xx/20xx
  const season = text.match(/\b(20\d{2})[-/](\d{2})\b/);
  const yr = text.match(/\b(19|20)\d{2}\b/);
  if (season) fields.year = season[1] + "-" + season[2];
  else if (yr) fields.year = yr[0];

  // Brand & set/product
  for (const b of BRANDS) if (upper.includes(b.toUpperCase())) { fields.brand = b; break; }
  for (const s of SETS) if (upper.includes(s.toUpperCase())) { fields.set_name = s; break; }

  // Card number — "#123", "No. 123", "Card 123", "RC-12"
  const num = text.match(/(?:card\s*(?:no\.?|number|#)?|no\.?|#)\s*[:#]?\s*([A-Z]{0,4}-?\d{1,4})\b/i);
  if (num && num[1] && /\d/.test(num[1])) fields.card_number = num[1].toUpperCase();

  // Sport from stat keywords
  let sport = "";
  for (const [sp, hints] of Object.entries(STAT_HINTS)) {
    if (hints.some((h) => upper.includes(h))) { sport = sp; break; }
  }
  // Team (and sport fallback from the team's league)
  let foundTeam = "";
  for (const [sp, teams] of Object.entries(TEAMS)) {
    for (const t of teams) {
      if (upper.includes(" " + t.toUpperCase() + " ")) { foundTeam = t; if (!sport) sport = sp; break; }
    }
    if (foundTeam) break;
  }
  if (foundTeam) fields.team = foundTeam;
  if (sport) fields.sport = sport;
  if (/\b(rookie|rc)\b/i.test(text)) fields.is_rookie = "yes";

  // Player — a 2-3 word alphabetic line that isn't a brand/set/team/keyword
  const candidate = lines.find((l) => {
    const words = l.split(" ");
    if (words.length < 2 || words.length > 3) return false;
    if (!/^[A-Za-z.'\- ]{5,28}$/.test(l)) return false;
    const U = l.toUpperCase();
    if (NAME_BANNED.some((w) => U.includes(w))) return false;
    if (foundTeam && U.includes(foundTeam.toUpperCase())) return false;
    return true;
  });
  if (candidate) fields.player = /[a-z]/.test(candidate) ? candidate : titleCase(candidate);

  return fields;
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

// Import a checklist straight from a file — creates the set (named from the
// file) and imports its rows, then opens it so you can fill in the details.
$("#cl-import-input").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  e.target.value = "";
  const base = file.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim();
  const set = await (await fetch("/api/checklists", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: base || "Imported checklist" }),
  })).json();
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch(`/api/checklists/${set.id}/import`, { method: "POST", body: fd });
  const res = await r.json().catch(() => ({}));
  if (r.ok) { await loadChecklists(); openChecklist(set.id); }
  else { alert(res.detail || "Import failed."); await loadChecklists(); openChecklist(set.id); }
});

// Save the set's details (name/year/brand/sport) after the fact
$("#cl-edit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const payload = { name: f.elements["name"].value, year: f.elements["year"].value, brand: f.elements["brand"].value, sport: f.elements["sport"].value };
  const r = await fetch("/api/checklists/" + state.checklistId, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (r.ok) { openChecklist(state.checklistId); loadChecklists(); } else alert("Could not save details.");
});

async function openChecklist(id) {
  state.checklistId = id;
  const d = await (await fetch("/api/checklists/" + id)).json();
  const s = d.set;
  $("#checklist-title").textContent = [s.year, s.brand, s.name].filter(Boolean).join(" ") || "Checklist";
  const ef = $("#cl-edit-form");
  ["name", "year", "brand", "sport"].forEach((k) => { if (ef.elements[k]) ef.elements[k].value = s[k] || ""; });
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

// ---------- Voice commands (free, browser Web Speech API) ----------
const SPORTS = ["Baseball", "Basketball", "Football", "Hockey", "Soccer"];

function openVoice() {
  $("#voice-transcript").textContent = "";
  $("#voice-result").innerHTML = "";
  $("#voice-mic").classList.remove("listening");
  $("#voice-modal").classList.remove("hidden");
}
function closeVoice() {
  try { if (voice.rec) voice.rec.stop(); } catch {}
  $("#voice-modal").classList.add("hidden");
}

const voice = { rec: null };

function startListening() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    $("#voice-result").innerHTML = '<p class="muted">Voice input isn\'t supported in this browser. Use Chrome or Safari on your laptop.</p>';
    return;
  }
  const rec = new SR();
  voice.rec = rec;
  rec.lang = "en-US";
  rec.interimResults = true;
  rec.maxAlternatives = 1;
  rec.continuous = false;
  let finalText = "";
  $("#voice-result").innerHTML = "";
  $("#voice-transcript").textContent = "Listening…";
  $("#voice-mic").classList.add("listening");

  rec.onresult = (e) => {
    let txt = "";
    for (const r of e.results) txt += r[0].transcript;
    $("#voice-transcript").textContent = txt;
    if (e.results[e.results.length - 1].isFinal) finalText = txt;
  };
  rec.onerror = (e) => {
    $("#voice-mic").classList.remove("listening");
    const msg = (e.error === "not-allowed" || e.error === "service-not-allowed")
      ? "Microphone blocked. On the laptop, allow mic access. (Voice needs a secure connection, so it works on the laptop at localhost but not over the phone's web address yet.)"
      : "Didn't catch that — tap the mic and try again.";
    $("#voice-transcript").textContent = "";
    $("#voice-result").innerHTML = `<p class="muted">${msg}</p>`;
  };
  rec.onend = () => {
    $("#voice-mic").classList.remove("listening");
    if (finalText) handleVoice(finalText);
  };
  try { rec.start(); } catch {
    $("#voice-result").innerHTML = '<p class="muted">Could not start the microphone. Use Chrome or Safari on your laptop.</p>';
  }
}

function parseInvId(low) {
  let m = low.match(/inv[\s-]*0*(\d{1,5})/);
  if (m) return "INV-" + String(m[1]).padStart(4, "0");
  m = low.match(/\b(?:number|card|id)\s+0*(\d{1,5})\b/);
  if (m) return "INV-" + String(m[1]).padStart(4, "0");
  return "";
}

function extractFieldsFromSpeech(t) {
  const fields = {};
  const low = " " + t.toLowerCase() + " ";
  const yr = t.match(/\b(20\d{2})[-/](\d{2})\b/) || t.match(/\b(19|20)\d{2}\b/);
  if (yr) fields.year = yr[0];
  for (const b of BRANDS) if (low.includes(" " + b.toLowerCase() + " ")) { fields.brand = b; break; }
  for (const s of SETS) if (low.includes(" " + s.toLowerCase() + " ")) { fields.set_name = s; break; }
  for (const sp of SPORTS) if (low.includes(" " + sp.toLowerCase() + " ")) { fields.sport = sp; break; }
  outer:
  for (const [sp, teams] of Object.entries(TEAMS)) {
    for (const tm of teams) {
      if (low.includes(" " + tm.toLowerCase() + " ")) { fields.team = tm; if (!fields.sport) fields.sport = sp; break outer; }
    }
  }
  if (/\brookie\b|\brc\b/.test(low)) fields.is_rookie = "yes";
  const num = t.match(/(?:number|no\.?|#)\s*([A-Za-z]{0,4}-?\d{1,4})/i);
  if (num && /\d/.test(num[1])) fields.card_number = num[1].toUpperCase();

  // Player = leftover words once known keywords/numbers are removed
  let rest = " " + t + " ";
  rest = rest.replace(/\b(19|20)\d{2}(?:[-/]\d{2})?\b/g, " ").replace(/#/g, " ").replace(/\b\d+\b/g, " ");
  const remove = [...BRANDS, ...SETS, ...SPORTS, fields.team || "",
    "add", "new", "log", "create", "enter", "card", "rookie", "rc", "number", "season", "of", "a", "an", "the"];
  remove.forEach((w) => { if (w) rest = rest.replace(new RegExp("\\b" + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "ig"), " "); });
  rest = rest.replace(/\s+/g, " ").trim();
  if (rest) fields.player = rest.split(" ").slice(0, 3).map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  return fields;
}

function parseVoiceCommand(t) {
  const low = t.toLowerCase();
  if (/\bsold\b|\bsell\b/.test(low)) {
    const pm = low.match(/(?:for|at)\s*\$?\s*([\d,]+(?:\.\d{1,2})?)/) || low.match(/\$\s*([\d,]+(?:\.\d{1,2})?)/);
    const price = pm ? parseFloat(pm[1].replace(/,/g, "")) : null;
    let key = parseInvId(low);
    if (!key) key = low.replace(/.*\b(?:mark|sell|sold)\b/, "").replace(/\bsold\b.*/, "").replace(/\bfor\b.*/, "").trim();
    return { intent: "sale", key, price, raw: t };
  }
  if (/\blist(ed|ing)?\b/.test(low) && !/^\s*(add|new|log|create|enter)\b/.test(low)) {
    let key = parseInvId(low);
    if (!key) key = low.replace(/.*\b(?:mark|list|listed)\b/, "").replace(/\blisted?\b.*/, "").trim();
    return { intent: "list", key, raw: t };
  }
  if (/^\s*(add|new|log|create|enter)\b/.test(low) || /\bcard\b/.test(low)) {
    return { intent: "add", fields: extractFieldsFromSpeech(t), raw: t };
  }
  return { intent: "unknown", raw: t };
}

async function handleVoice(text) {
  const cmd = parseVoiceCommand(text);
  const box = $("#voice-result");
  if (cmd.intent === "add") {
    const sum = ["year", "brand", "set_name", "player", "sport", "card_number"].map((k) => cmd.fields[k]).filter(Boolean).join(" ");
    box.innerHTML = `<div class="voice-card"><b>Add a card</b><div class="vc-sum">${esc(sum || "(no details caught — you can fill them in)")}</div><button id="v-add" class="btn btn-primary">Review &amp; save →</button></div>`;
    $("#v-add").onclick = () => { closeVoice(); showAddReview(cmd.fields); };
  } else if (cmd.intent === "sale" || cmd.intent === "list") {
    if (!cmd.key) { box.innerHTML = '<p class="muted">Tell me which card, e.g. “mark INV 5 sold for 200”.</p>'; return; }
    const cards = await (await fetch("/api/cards?q=" + encodeURIComponent(cmd.key))).json();
    if (!cards.length) { box.innerHTML = `<p class="muted">Couldn't find a card matching “${esc(cmd.key)}”.</p>`; return; }
    const c = cards[0];
    const action = cmd.intent === "sale"
      ? `Mark <b>${esc(c.card_id)} ${esc(c.player || "")}</b> as <b>SOLD</b>${cmd.price ? " for " + money(cmd.price) : ""}?`
      : `Mark <b>${esc(c.card_id)} ${esc(c.player || "")}</b> as <b>LISTED</b>?`;
    box.innerHTML = `<div class="voice-card"><div>${action}</div><button id="v-confirm" class="btn btn-primary">Confirm</button></div>`;
    $("#v-confirm").onclick = async () => {
      const payload = cmd.intent === "sale" ? { status: "sold", sale_price: cmd.price ?? null } : { status: "listed" };
      await fetch("/api/cards/" + c.id, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      closeVoice();
      loadInventory();
    };
  } else {
    box.innerHTML = '<p class="muted">Didn\'t catch a command. Try “add a 2021 Topps Mike Trout baseball” or “mark INV 5 sold for 200”.</p>';
  }
}

function showAddReview(fields) {
  showView("add");
  state.uploaded = { front_image: "", back_image: "" };
  const f = $("#review-form");
  f.reset();
  Object.entries(fields).forEach(([k, v]) => { if (f.elements[k] && v) f.elements[k].value = v; });
  $("#vision-note").textContent = "🎤 From your voice command — check the details and Save.";
  $("#capture-step").classList.add("hidden");
  $("#review-form").classList.remove("hidden");
}

$("#voice-fab").addEventListener("click", openVoice);
$("#voice-close").addEventListener("click", closeVoice);
$("#voice-mic").addEventListener("click", startListening);

loadInventory();

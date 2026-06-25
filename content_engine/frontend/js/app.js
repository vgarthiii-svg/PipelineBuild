/* Content Creator Engine — SPA controller (vanilla JS, no build step). */

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const $ = (sel, root = document) => root.querySelector(sel);
const view = () => $("#view");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const nl2br = (s) => esc(s).replace(/\n/g, "<br>");
let META = null;
let TOAST_T = null;

function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show" + (err ? " err" : "");
  clearTimeout(TOAST_T);
  TOAST_T = setTimeout(() => (t.className = "toast"), 3200);
}
function modal(html) {
  $("#modal-body").innerHTML = html;
  $("#modal").classList.remove("hidden");
}
function closeModal() { $("#modal").classList.add("hidden"); }
$("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });

function scoreColor(v) {
  if (v >= 85) return "var(--good)";
  if (v >= 70) return "var(--accent)";
  if (v >= 50) return "var(--warn)";
  return "var(--bad)";
}
function ring(val) {
  const c = scoreColor(val);
  return `<div class="ring" style="--val:${val};--ring-c:${c}"><div class="ring-inner" style="color:${c}">${val}</div></div>`;
}
function badge(status) {
  return `<span class="badge ${esc(status)}">${esc((status || "").replace("_", " "))}</span>`;
}
function csvToList(s) { return (s || "").split(",").map((x) => x.trim()).filter(Boolean); }
async function busy(btn, fn) {
  const old = btn.innerHTML; btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> ${old}`;
  try { return await fn(); }
  catch (e) { toast(e.message || "Error", true); throw e; }
  finally { btn.disabled = false; btn.innerHTML = old; }
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------
const ROUTES = {};
function route(name, arg) {
  location.hash = arg !== undefined ? `#/${name}/${arg}` : `#/${name}`;
}
async function render() {
  const parts = (location.hash || "#/dashboard").slice(2).split("/");
  const name = parts[0] || "dashboard";
  const arg = parts[1];
  document.querySelectorAll(".nav-item").forEach((n) =>
    n.classList.toggle("active", n.dataset.route === name));
  const fn = ROUTES[name] || ROUTES.dashboard;
  view().innerHTML = `<div class="loading">Loading…</div>`;
  try { await fn(arg); } catch (e) { view().innerHTML = `<div class="empty">⚠️ ${esc(e.message)}</div>`; }
}
window.addEventListener("hashchange", render);
document.querySelectorAll(".nav-item").forEach((n) =>
  n.addEventListener("click", () => route(n.dataset.route)));

function crumb(t) { $("#crumb").textContent = t; }

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------
ROUTES.dashboard = async () => {
  crumb("Dashboard");
  const [projects, brands, lib] = await Promise.all([API.projects(), API.brands(), API.library()]);
  const byStatus = {};
  projects.forEach((p) => (byStatus[p.status] = (byStatus[p.status] || 0) + 1));
  const scored = lib.items.filter((i) => i.score != null);
  const avg = scored.length ? Math.round(scored.reduce((a, b) => a + b.score, 0) / scored.length) : 0;

  view().innerHTML = `
    <div class="grid grid-4">
      ${statCard("Projects", projects.length, "All content projects")}
      ${statCard("Brand Profiles", brands.length, "Reusable brand voices")}
      ${statCard("Library Items", lib.count, "Saved drafts")}
      ${statCard("Avg Score", avg || "—", "Across scored drafts")}
    </div>
    <div class="grid grid-2" style="margin-top:16px">
      <div class="card">
        <div class="card-h"><h3>Pipeline by status</h3></div>
        ${META.statuses.map((s) => `<div style="display:flex;justify-content:space-between;padding:6px 0">
            ${badge(s)}<b>${byStatus[s] || 0}</b></div>`).join("")}
      </div>
      <div class="card">
        <div class="card-h"><h3>Recent projects</h3><button class="btn btn-sm" onclick="route('new')">+ New</button></div>
        ${projects.slice(0, 6).map((p) => `<div class="row-link" onclick="route('project','${p.id}')"
            style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border)">
            <div><b>${esc(p.title)}</b><div class="muted" style="font-size:12px">${esc(p.platform)} · ${esc(p.content_type)}</div></div>
            ${badge(p.status)}</div>`).join("") || `<div class="empty">No projects yet. Click “New Content”.</div>`}
      </div>
    </div>
    <div class="card" style="margin-top:16px">
      <div class="card-h"><h3>Workflow</h3><span class="muted">Brand → Research → Draft → Score → Revise → Repurpose → Library</span></div>
      <div class="chips">
        ${["1. Brand profile","2. Platform","3. Content type","4. Objective","5. Audience","6. Product","7. Tone","8. CTA","9. Research","10. Strategy brief","11. Draft","12. Score","13. Improve","14. Export","15. Library"].map((s) => `<span class="chip">${s}</span>`).join("")}
      </div>
    </div>`;
};
const statCard = (label, val, sub) =>
  `<div class="card"><div class="stat-label">${label}</div><div class="stat">${val}</div><div class="muted" style="font-size:12px">${sub}</div></div>`;

// ---------------------------------------------------------------------------
// New Content wizard
// ---------------------------------------------------------------------------
ROUTES.new = async () => {
  crumb("New Content");
  const brands = await API.brands();
  const m = META;
  const opt = (arr, v) => arr.map((x) => {
    const val = typeof x === "object" ? x.value : x;
    const lbl = typeof x === "object" ? x.label : x;
    return `<option value="${esc(val)}" ${v === val ? "selected" : ""}>${esc(lbl)}</option>`;
  }).join("");

  view().innerHTML = `
    <div class="steps">${["Brand & platform","Content & goal","Audience & product","Voice & CTA"].map((s, i) =>
      `<span class="step ${i === 0 ? "active" : ""}" data-step="${i}">${i + 1}. ${s}</span>`).join("")}</div>
    <form id="wiz" class="card">
      <div class="field-row">
        <div><label>Brand profile</label><select name="brand_id">
          <option value="">— None / ad-hoc —</option>
          ${brands.map((b) => `<option value="${b.id}">${esc(b.name)}</option>`).join("")}
        </select></div>
        <div><label>Title</label><input name="title" placeholder="e.g. Q3 feature launch post" required></div>
      </div>
      <div class="field-row-3">
        <div><label>Platform</label><select name="platform">${opt(m.platforms)}</select></div>
        <div><label>Content type</label><select name="content_type">${opt(m.content_types)}</select></div>
        <div><label>Campaign</label><input name="campaign" placeholder="optional"></div>
      </div>
      <hr class="sep">
      <div class="field-row">
        <div><label>Business goal</label><select name="business_goal">${opt(m.business_goals)}</select></div>
        <div><label>Funnel stage</label><select name="funnel_stage">${opt(m.funnel_stages)}</select></div>
      </div>
      <label>Objective / what this content must achieve</label>
      <textarea name="objective" placeholder="e.g. Announce our new analytics dashboard and drive demo bookings"></textarea>
      <hr class="sep">
      <div class="field-row">
        <div><label>Target audience</label><input name="target_audience" placeholder="e.g. RevOps leaders at mid-market SaaS"></div>
        <div><label>Geographic market</label><input name="geo_market" placeholder="e.g. North America"></div>
      </div>
      <div class="field-row">
        <div><label>Offer / service promoted</label><input name="offer" placeholder="e.g. 14-day free trial"></div>
        <div><label>Industry</label><input name="industry" placeholder="e.g. SaaS"></div>
      </div>
      <div class="field-row">
        <div><label>Keywords (comma-separated)</label><input name="keywords" placeholder="analytics, revops, reporting"></div>
        <div><label>Competitors (comma-separated)</label><input name="competitors" placeholder="Acme, Globex"></div>
      </div>
      <hr class="sep">
      <div class="field-row-3">
        <div><label>Tone</label><select name="tone">${opt(m.tones)}</select></div>
        <div><label>Length</label><select name="length">${opt(m.lengths, "medium")}</select></div>
        <div><label>CTA</label><input name="cta" placeholder="e.g. Book a demo"></div>
      </div>
      <div class="field-row">
        <div><label>Compliance considerations</label><input name="compliance" placeholder="e.g. no performance guarantees"></div>
        <div><label>Desired outcome</label><input name="desired_outcome" placeholder="e.g. 50 demo bookings"></div>
      </div>
      <div class="btn-row" style="margin-top:18px">
        <button type="submit" class="btn btn-primary">Create & open workspace →</button>
        <button type="button" class="btn btn-ghost" onclick="route('dashboard')">Cancel</button>
      </div>
    </form>`;

  $("#wiz").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const payload = Object.fromEntries(f.entries());
    payload.brand_id = payload.brand_id ? Number(payload.brand_id) : null;
    payload.keywords = csvToList(payload.keywords);
    payload.competitors = csvToList(payload.competitors);
    const btn = e.submitter;
    const p = await busy(btn, () => API.createProject(payload));
    toast("Project created");
    route("project", p.id);
  });
};

// ---------------------------------------------------------------------------
// Project workspace: research -> generate -> draft editor -> score
// ---------------------------------------------------------------------------
ROUTES.project = async (id) => {
  const p = await API.project(id);
  crumb(p.title);
  const [brief, drafts] = await Promise.all([API.getResearch(id), API.drafts(id)]);
  const draft = drafts[0] || null;

  view().innerHTML = `
    <div class="card-h">
      <div><h3 style="margin:0">${esc(p.title)} ${badge(p.status)}</h3>
        <div class="muted" style="font-size:13px">${esc(p.platform)} · ${esc(p.content_type)} · ${esc(p.business_goal || "")} · ${esc(p.funnel_stage || "")}</div></div>
      <div class="btn-row">
        <button class="btn" id="btn-research">🔎 ${brief ? "Re-run research" : "Run research"}</button>
        <button class="btn btn-primary" id="btn-generate">✨ ${draft ? "Regenerate draft" : "Generate draft"}</button>
      </div>
    </div>
    <div id="brief-area"></div>
    <div id="draft-area"></div>`;

  renderBrief(brief);
  if (draft) renderEditor(draft, p);
  else $("#draft-area").innerHTML = `<div class="empty">No draft yet. Run research, then generate a draft.</div>`;

  $("#btn-research").addEventListener("click", (e) => busy(e.target, async () => {
    const b = await API.research(id); toast("Research brief generated"); renderBrief(b);
  }));
  $("#btn-generate").addEventListener("click", (e) => busy(e.target, async () => {
    const d = await API.generate(id); toast("Draft generated"); renderEditor(d, p);
  }));
};

function renderBrief(b) {
  const area = $("#brief-area");
  if (!b) { area.innerHTML = ""; return; }
  const list = (arr) => (arr || []).map((x) => `<li>${esc(x)}</li>`).join("");
  area.innerHTML = `
    <div class="card" style="margin-top:16px">
      <div class="card-h"><h3>🔎 Research brief</h3>
        <span class="muted" style="font-size:12px">${esc(b.model_used)} · ${new Date(b.generated_at).toLocaleString()}</span></div>
      <div class="grid grid-2">
        <div><b class="muted">Recommended angle</b><p>${esc(b.recommended_angle) || "—"}</p>
          <b class="muted">Recommended hook</b><p>${esc(b.recommended_hook) || "—"}</p>
          <b class="muted">Search intent</b><p>${esc(b.search_intent) || "—"}</p>
          <b class="muted">Risks / compliance</b><p>${esc(b.risks) || "—"}</p></div>
        <div>
          <b class="muted">Trends</b><ul class="list-disc">${list(b.trends)}</ul>
          <b class="muted">High-performing patterns</b><ul class="list-disc">${list(b.high_performing_patterns)}</ul>
          <b class="muted">Audience pain points</b><ul class="list-disc">${list(b.audience_pain_points)}</ul>
          <b class="muted">Content gaps</b><ul class="list-disc">${list(b.content_gaps)}</ul>
        </div>
      </div>
      <hr class="sep">
      <div class="chips">${(b.keywords || []).map((k) => `<span class="chip">🔑 ${esc(k)}</span>`).join("")}</div>
    </div>`;
}

function renderEditor(d, p) {
  const area = $("#draft-area");
  const actions = META.editor_actions;
  area.innerHTML = `
    <div class="editor-layout" style="margin-top:16px">
      <div class="card">
        <div class="card-h"><h3>📝 Draft editor <span class="muted" style="font-weight:400">v${d.version} · ${esc(d.model_used)}</span></h3>
          <div class="btn-row">
            <button class="btn btn-sm" id="save-draft">💾 Save</button>
            <button class="btn btn-sm btn-good" id="finalize-draft">✅ Finalize</button>
          </div></div>
        <div class="editor-toolbar">
          ${actions.map((a) => `<button class="btn btn-sm" data-action="${a.action}">${esc(a.label)}</button>`).join("")}
          <button class="btn btn-sm" id="repurpose-btn">♻️ Repurpose</button>
          <button class="btn btn-sm" id="export-btn">⬇️ Export</button>
        </div>
        <input id="draft-title" value="${esc(d.title)}" style="font-weight:700;margin-bottom:10px">
        <textarea class="editor-body" id="draft-body">${esc(d.body)}</textarea>
      </div>
      <div>
        <div class="card"><div class="card-h"><h3>📊 Scorecard</h3>
          <button class="btn btn-sm btn-primary" id="score-btn">Score draft</button></div>
          <div id="score-panel"><div class="muted">Click “Score draft” to evaluate across 14 categories.</div></div>
        </div>
        ${optionsCard("Headline / hook options", d.headline_options)}
        ${optionsCard("CTA options", d.cta_options)}
        ${d.rationale ? `<div class="card"><h3>💡 Rationale</h3><p style="font-size:13px">${nl2br(d.rationale)}</p></div>` : ""}
        ${d.posting_guidance ? `<div class="card"><h3>📌 Posting guidance</h3><p style="font-size:13px">${nl2br(d.posting_guidance)}</p></div>` : ""}
      </div>
    </div>`;

  const getBody = () => $("#draft-body").value;
  area.querySelectorAll("[data-action]").forEach((btn) =>
    btn.addEventListener("click", () => busy(btn, async () => {
      const updated = await API.revise(d.id, { action: btn.dataset.action, body: getBody() });
      $("#draft-body").value = updated.body; toast("Revised: " + btn.dataset.action);
    })));
  $("#save-draft").addEventListener("click", (e) => busy(e.target, async () => {
    await API.saveBody(d.id, { body: getBody(), title: $("#draft-title").value }); toast("Saved");
  }));
  $("#finalize-draft").addEventListener("click", (e) => busy(e.target, async () => {
    await API.saveBody(d.id, { body: getBody(), title: $("#draft-title").value });
    await API.finalize(d.id); toast("Finalized & approved"); route("project", p.id);
  }));
  $("#score-btn").addEventListener("click", (e) => busy(e.target, async () => {
    await API.saveBody(d.id, { body: getBody(), title: $("#draft-title").value });
    const s = await API.score(d.id); renderScore(s);
  }));
  $("#repurpose-btn").addEventListener("click", (e) => busy(e.target, async () => {
    const r = await API.repurpose(d.id, { body: getBody() }); showRepurpose(r.outputs);
  }));
  $("#export-btn").addEventListener("click", () => showExport(d.id));
  API.getScore(d.id).then((s) => { if (s) renderScore(s); });
}

const optionsCard = (title, opts) => !opts || !opts.length ? "" :
  `<div class="card"><h3>${esc(title)}</h3><div class="options-list">
    ${opts.map((o) => `<div class="option"><span>${esc(o)}</span>
      <button class="btn btn-sm btn-ghost" onclick="navigator.clipboard.writeText('${esc(o).replace(/'/g, "\\'")}');toast('Copied')">copy</button></div>`).join("")}
  </div></div>`;

function renderScore(s) {
  const cats = s.categories;
  $("#score-panel").innerHTML = `
    <div style="display:flex;gap:14px;align-items:center;margin-bottom:12px">
      ${ring(s.overall)}<div><b>${s.overall >= 85 ? "Excellent" : s.overall >= 70 ? "Strong" : s.overall >= 50 ? "Needs work" : "Weak"}</b>
      <div class="muted" style="font-size:12px">${esc(s.summary)}</div></div></div>
    <div class="score-grid">
      ${Object.entries(cats).map(([k, c]) => `
        <div class="score-cat" title="${esc(c.weak)}">
          <div class="top"><span style="font-size:12px">${esc(c.label || k)}</span><b style="color:${scoreColor(c.score)}">${c.score}</b></div>
          <div class="bar"><i style="width:${c.score}%;background:${scoreColor(c.score)}"></i></div>
          <div class="muted" style="font-size:11px">${esc((c.improvements || [])[0] || "")}</div>
        </div>`).join("")}
    </div>`;
}

function showRepurpose(outputs) {
  modal(`<div class="card-h"><h3>♻️ Repurposed content</h3><button class="btn btn-sm" onclick="closeModal()">Close</button></div>
    ${outputs.map((o) => `<div style="margin-bottom:14px">
      <b>${esc(o.format)}</b>
      <button class="btn btn-sm btn-ghost" onclick="navigator.clipboard.writeText(${JSON.stringify(o.content)});toast('Copied')">copy</button>
      <div class="card" style="margin-top:6px;font-size:13px">${nl2br(o.content)}</div></div>`).join("")}`);
}

function showExport(id) {
  const fmts = [["markdown", "Markdown"], ["html", "HTML"], ["text", "Plain text"], ["csv", "CSV"], ["docx", "DOCX"]];
  modal(`<div class="card-h"><h3>⬇️ Export draft</h3><button class="btn btn-sm" onclick="closeModal()">Close</button></div>
    <div class="btn-row">${fmts.map(([f, l]) =>
      `<a class="btn" href="${API.exportUrl(id, f)}" target="_blank" download>${l}</a>`).join("")}</div>
    <p class="muted" style="margin-top:12px;font-size:12px">For PDF, open the HTML export and print to PDF.</p>`);
}

// ---------------------------------------------------------------------------
// Library
// ---------------------------------------------------------------------------
ROUTES.library = async () => {
  crumb("Content Library");
  const lib = await API.library();
  const platforms = [...new Set(lib.items.map((i) => i.platform).filter(Boolean))];
  view().innerHTML = `
    <div class="card">
      <div class="btn-row" style="margin-bottom:14px">
        <input id="lib-q" placeholder="Search title, body, campaign…" style="max-width:300px">
        <select id="lib-platform"><option value="">All platforms</option>${platforms.map((p) => `<option>${esc(p)}</option>`).join("")}</select>
        <select id="lib-status"><option value="">All statuses</option>${META.statuses.map((s) => `<option>${esc(s)}</option>`).join("")}</select>
        <button class="btn" id="lib-search">Search</button>
      </div>
      <div id="lib-table"></div>
    </div>`;
  const draw = (items) => {
    $("#lib-table").innerHTML = items.length ? `
      <table><thead><tr><th>Title</th><th>Platform</th><th>Type</th><th>Status</th><th>Score</th><th>Ver</th><th>Created</th></tr></thead>
      <tbody>${items.map((i) => `<tr class="row-link" onclick="route('project','${i.project_id}')">
        <td><b>${esc(i.title)}</b> ${i.is_final ? "✅" : ""}</td><td>${esc(i.platform)}</td><td>${esc(i.content_type)}</td>
        <td>${badge(i.status)}</td><td>${i.score != null ? `<b style="color:${scoreColor(i.score)}">${i.score}</b>` : "—"}</td>
        <td>v${i.version}</td><td class="muted">${new Date(i.created_at).toLocaleDateString()}</td></tr>`).join("")}</tbody></table>`
      : `<div class="empty">No content yet. Create your first piece.</div>`;
  };
  draw(lib.items);
  $("#lib-search").addEventListener("click", async () => {
    const params = {};
    if ($("#lib-q").value) params.q = $("#lib-q").value;
    if ($("#lib-platform").value) params.platform = $("#lib-platform").value;
    if ($("#lib-status").value) params.status = $("#lib-status").value;
    draw((await API.library(params)).items);
  });
};

// ---------------------------------------------------------------------------
// Brands
// ---------------------------------------------------------------------------
ROUTES.brands = async () => {
  crumb("Brand Profiles");
  const brands = await API.brands();
  view().innerHTML = `
    <div class="card-h"><h3>Brand profiles</h3><button class="btn btn-primary" onclick="route('brand','new')">+ New brand</button></div>
    <div class="grid grid-3">
      ${brands.map((b) => `<div class="card row-link" onclick="route('brand','${b.id}')">
        <h3>${esc(b.name)}</h3>
        <div class="muted" style="font-size:13px">${esc(b.industry || "—")}</div>
        <p style="font-size:13px">${esc((b.brand_voice || "No voice defined").slice(0, 90))}</p>
        <div class="chips">${(b.words_to_use || []).slice(0, 4).map((w) => `<span class="tag">${esc(w)}</span>`).join("")}</div>
      </div>`).join("") || `<div class="empty">No brand profiles yet.</div>`}
    </div>`;
};

ROUTES.brand = async (id) => {
  const isNew = id === "new";
  const b = isNew ? {} : await API.brand(id);
  crumb(isNew ? "New Brand" : b.name);
  const tv = (v) => esc(Array.isArray(v) ? v.join(", ") : (v || ""));
  view().innerHTML = `
    <form id="brand-form" class="card">
      <div class="field-row">
        <div><label>Brand / profile name *</label><input name="name" value="${tv(b.name)}" required></div>
        <div><label>Company name</label><input name="company_name" value="${tv(b.company_name)}"></div>
      </div>
      <div class="field-row">
        <div><label>Website</label><input name="website" value="${tv(b.website)}"></div>
        <div><label>Industry</label><input name="industry" value="${tv(b.industry)}"></div>
      </div>
      <label>Audience</label><textarea name="audience">${tv(b.audience)}</textarea>
      <label>Products / services</label><textarea name="products_services">${tv(b.products_services)}</textarea>
      <label>Brand voice</label><textarea name="brand_voice">${tv(b.brand_voice)}</textarea>
      <div class="field-row">
        <div><label>Words to USE (comma-separated)</label><input name="words_to_use" value="${tv(b.words_to_use)}"></div>
        <div><label>Words to AVOID (comma-separated)</label><input name="words_to_avoid" value="${tv(b.words_to_avoid)}"></div>
      </div>
      <label>Competitors (comma-separated)</label><input name="competitors" value="${tv(b.competitors)}">
      <label>Differentiators</label><textarea name="differentiators">${tv(b.differentiators)}</textarea>
      <label>Proof points</label><textarea name="proof_points">${tv(b.proof_points)}</textarea>
      <label>Offers</label><textarea name="offers">${tv(b.offers)}</textarea>
      <div class="field-row">
        <div><label>Preferred CTA language</label><input name="preferred_cta_language" value="${tv(b.preferred_cta_language)}"></div>
        <div><label>Compliance rules</label><input name="compliance_rules" value="${tv(b.compliance_rules)}"></div>
      </div>
      <label>Approved boilerplate</label><textarea name="approved_boilerplate">${tv(b.approved_boilerplate)}</textarea>
      <label>Team notes</label><textarea name="team_notes">${tv(b.team_notes)}</textarea>
      <div class="btn-row" style="margin-top:18px">
        <button type="submit" class="btn btn-primary">${isNew ? "Create brand" : "Save changes"}</button>
        ${isNew ? "" : `<button type="button" class="btn" id="del-brand">Delete</button>`}
        <button type="button" class="btn btn-ghost" onclick="route('brands')">Cancel</button>
      </div>
    </form>`;

  $("#brand-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    ["words_to_use", "words_to_avoid", "competitors"].forEach((k) => (data[k] = csvToList(data[k])));
    await busy(e.submitter, () => isNew ? API.createBrand(data) : API.updateBrand(id, data));
    toast("Brand saved"); route("brands");
  });
  if (!isNew) $("#del-brand").addEventListener("click", async () => {
    if (confirm("Delete this brand profile?")) { await API.deleteBrand(id); toast("Deleted"); route("brands"); }
  });
};

// ---------------------------------------------------------------------------
// Calendar
// ---------------------------------------------------------------------------
ROUTES.calendar = async () => {
  crumb("Content Calendar");
  const [entries, projects] = await Promise.all([API.calendar(), API.projects()]);
  view().innerHTML = `
    <div class="grid grid-2">
      <div class="card"><h3>Add to calendar</h3>
        <form id="cal-form">
          <label>Title</label><input name="title" required>
          <div class="field-row">
            <div><label>Platform</label><input name="platform"></div>
            <div><label>Date</label><input type="datetime-local" name="scheduled_date" required></div>
          </div>
          <label>Link project (optional)</label>
          <select name="project_id"><option value="">—</option>${projects.map((p) => `<option value="${p.id}">${esc(p.title)}</option>`).join("")}</select>
          <label>Notes</label><textarea name="notes"></textarea>
          <button class="btn btn-primary" style="margin-top:12px">Schedule</button>
        </form>
      </div>
      <div class="card"><h3>Scheduled (${entries.length})</h3>
        ${entries.map((e) => `<div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border)">
          <div><b>${esc(e.title)}</b><div class="muted" style="font-size:12px">${esc(e.platform || "")} · ${new Date(e.scheduled_date).toLocaleString()}</div></div>
          <button class="btn btn-sm btn-ghost" onclick="API.delCalendar(${e.id}).then(()=>{toast('Removed');render()})">✕</button>
        </div>`).join("") || `<div class="empty">Nothing scheduled.</div>`}
      </div>
    </div>`;
  $("#cal-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(e.target).entries());
    d.project_id = d.project_id ? Number(d.project_id) : null;
    d.scheduled_date = new Date(d.scheduled_date).toISOString();
    await busy(e.submitter, () => API.addCalendar(d)); toast("Scheduled"); render();
  });
};

// ---------------------------------------------------------------------------
// Style Guide
// ---------------------------------------------------------------------------
ROUTES.styleguide = async () => {
  crumb("Style Guide");
  const rules = await API.styleRules();
  view().innerHTML = `
    <div class="grid grid-2">
      <div class="card"><h3>📐 AP-style checker</h3>
        <textarea id="ap-text" placeholder="Paste content to check against AP-style + your custom rules…" style="min-height:140px"></textarea>
        <button class="btn btn-primary" id="ap-run" style="margin-top:10px">Check</button>
        <div id="ap-result" style="margin-top:14px"></div>
      </div>
      <div class="card"><h3>Editorial rules</h3>
        <form id="rule-form" style="margin-bottom:14px">
          <div class="field-row">
            <div><label>Rule name</label><input name="name" required></div>
            <div><label>Severity</label><select name="severity"><option>info</option><option selected>warning</option><option>error</option></select></div>
          </div>
          <label>Rule description</label><input name="rule" required>
          <div class="field-row">
            <div><label>Detect type</label><select name="dtype"><option value="phrase">phrase list</option><option value="regex">regex</option></select></div>
            <div><label>Pattern (comma-separated phrases or regex)</label><input name="pattern"></div>
          </div>
          <button class="btn btn-primary" style="margin-top:10px">Add rule</button>
        </form>
        <div id="rules-list">${rules.map(ruleRow).join("")}</div>
      </div>
    </div>`;

  $("#ap-run").addEventListener("click", (e) => busy(e.target, async () => {
    const r = await API.apCheck($("#ap-text").value);
    $("#ap-result").innerHTML = `
      <div style="display:flex;gap:12px;align-items:center">${ring(r.ap_score)}
        <div><b>${r.passes ? "Passes" : "Needs edits"}</b><div class="muted" style="font-size:12px">${r.word_count} words · ${r.findings.length} findings</div></div></div>
      <ul class="list-disc" style="margin-top:10px">${r.findings.map((f) =>
        `<li><b>${esc(f.rule)}</b> <span class="tag">${esc(f.severity)}</span> — ${esc(f.message)} ${f.matches.length ? `<span class="muted">(${f.matches.slice(0,5).map(esc).join(", ")})</span>` : ""}</li>`).join("") || "<li class='muted'>No issues found 🎉</li>"}</ul>`;
  }));
  $("#rule-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(e.target).entries());
    const payload = { name: d.name, rule: d.rule, severity: d.severity, category: "custom",
      detection: { type: d.dtype, pattern: d.pattern, message: d.rule } };
    await busy(e.submitter, () => API.createStyleRule(payload)); toast("Rule added"); render();
  });
};
function ruleRow(r) {
  return `<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border)">
    <div><b>${esc(r.name)}</b> <span class="tag">${esc(r.severity)}</span> ${r.is_system ? '<span class="muted" style="font-size:11px">system</span>' : ""}
      <div class="muted" style="font-size:12px">${esc(r.rule)}</div></div>
    <div class="btn-row">
      <button class="btn btn-sm" onclick="API.toggleStyleRule(${r.id}).then(()=>{toast('Toggled');render()})">${r.enabled ? "On" : "Off"}</button>
      ${r.is_system ? "" : `<button class="btn btn-sm btn-ghost" onclick="API.delStyleRule(${r.id}).then(()=>{toast('Deleted');render()})">✕</button>`}
    </div></div>`;
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
ROUTES.settings = async () => {
  crumb("Settings");
  const [rules, snippets, appS, health] = await Promise.all([
    API.platformRules(), API.snippets(), API.appSettings(), API.health()]);
  view().innerHTML = `
    <div class="card"><h3>AI & providers</h3>
      <div class="kv">
        <b>AI provider</b><div>${esc(health.ai_provider)} ${health.ai_enabled ? '<span class="tag">live</span>' : '<span class="tag">mock — set ANTHROPIC_API_KEY</span>'}</div>
        <b>Research</b><div>${health.research_enabled ? '<span class="tag">live web research</span>' : '<span class="tag">synthesized</span>'}</div>
      </div>
      <label>Default export format</label>
      <select id="def-export">${["markdown","html","text","csv","docx"].map((f) => `<option ${appS.default_export === f ? "selected" : ""}>${f}</option>`).join("")}</select>
      <button class="btn btn-sm" style="margin-top:10px" id="save-export">Save</button>
    </div>
    <div class="grid grid-2" style="margin-top:16px">
      <div class="card"><h3>Saved snippets (CTAs / offers / audiences)</h3>
        <form id="snip-form" style="margin-bottom:12px">
          <div class="field-row-3">
            <select name="kind"><option value="cta">CTA</option><option value="offer">Offer</option><option value="audience">Audience</option><option value="compliance">Compliance</option></select>
            <input name="label" placeholder="label" required>
            <input name="value" placeholder="value">
          </div>
          <button class="btn btn-sm btn-primary" style="margin-top:8px">Add</button>
        </form>
        ${snippets.map((s) => `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border)">
          <div><span class="tag">${esc(s.kind)}</span> <b>${esc(s.label)}</b> <span class="muted">${esc(s.value)}</span></div>
          <button class="btn btn-sm btn-ghost" onclick="API.delSnippet(${s.id}).then(()=>{toast('Deleted');render()})">✕</button></div>`).join("") || '<div class="muted">No snippets yet.</div>'}
      </div>
      <div class="card"><h3>Platform rules (${rules.length})</h3>
        <div style="max-height:420px;overflow:auto">${rules.map((r) => `
          <div style="padding:8px 0;border-bottom:1px solid var(--border)">
            <b>${esc(r.label)}</b> <span class="muted" style="font-size:12px">${esc(r.platform)}/${esc(r.content_type)}</span>
            <div class="muted" style="font-size:12px">${(r.structure || []).join(" → ")}</div>
          </div>`).join("")}</div>
      </div>
    </div>`;
  $("#save-export").addEventListener("click", async () => {
    await API.setAppSetting({ key: "default_export", value: $("#def-export").value }); toast("Saved");
  });
  $("#snip-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    await busy(e.submitter, () => API.createSnippet(Object.fromEntries(new FormData(e.target).entries())));
    toast("Added"); render();
  });
};

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
(async function boot() {
  try {
    META = await API.meta();
    const s = $("#ai-status");
    s.textContent = "AI: " + (META.ai_enabled ? "live" : "mock");
    s.className = "pill " + (META.ai_enabled ? "on" : "off");
  } catch (e) {
    view().innerHTML = `<div class="empty">⚠️ Cannot reach API: ${esc(e.message)}</div>`;
    return;
  }
  if (!location.hash) location.hash = "#/dashboard";
  render();
})();
window.route = route; window.toast = toast; window.closeModal = closeModal;
window.render = render; window.API = API;

/* Thin fetch wrapper around the Content Engine API. */
const API = (() => {
  const base = "";
  async function req(method, path, body) {
    const opts = { method, headers: { "Content-Type": "application/json" } };
    if (body !== undefined) opts.body = JSON.stringify(body);
    const res = await fetch(base + path, opts);
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch (e) {}
      throw new Error(detail);
    }
    if (res.status === 204) return null;
    const ct = res.headers.get("content-type") || "";
    return ct.includes("application/json") ? res.json() : res.text();
  }
  return {
    get: (p) => req("GET", p),
    post: (p, b) => req("POST", p, b),
    put: (p, b) => req("PUT", p, b),
    del: (p) => req("DELETE", p),

    meta: () => req("GET", "/api/meta"),
    health: () => req("GET", "/api/health"),

    brands: () => req("GET", "/api/brands"),
    brand: (id) => req("GET", `/api/brands/${id}`),
    createBrand: (b) => req("POST", "/api/brands", b),
    updateBrand: (id, b) => req("PUT", `/api/brands/${id}`, b),
    deleteBrand: (id) => req("DELETE", `/api/brands/${id}`),

    projects: () => req("GET", "/api/projects"),
    project: (id) => req("GET", `/api/projects/${id}`),
    createProject: (p) => req("POST", "/api/projects", p),
    updateProject: (id, p) => req("PUT", `/api/projects/${id}`, p),
    deleteProject: (id) => req("DELETE", `/api/projects/${id}`),
    research: (id) => req("POST", `/api/projects/${id}/research`),
    getResearch: (id) => req("GET", `/api/projects/${id}/research`),
    generate: (id) => req("POST", `/api/projects/${id}/generate`),
    drafts: (id) => req("GET", `/api/projects/${id}/drafts`),

    draft: (id) => req("GET", `/api/drafts/${id}`),
    saveBody: (id, b) => req("PUT", `/api/drafts/${id}/body`, b),
    score: (id) => req("POST", `/api/drafts/${id}/score`),
    getScore: (id) => req("GET", `/api/drafts/${id}/score`),
    revise: (id, b) => req("POST", `/api/drafts/${id}/revise`, b),
    repurpose: (id, b) => req("POST", `/api/drafts/${id}/repurpose`, b),
    finalize: (id) => req("POST", `/api/drafts/${id}/finalize`),
    addTag: (id, b) => req("POST", `/api/drafts/${id}/tags`, b),
    exportUrl: (id, fmt) => `/api/drafts/${id}/export/${fmt}`,

    library: (params) => req("GET", "/api/library" + (params ? "?" + new URLSearchParams(params) : "")),

    calendar: () => req("GET", "/api/calendar"),
    addCalendar: (b) => req("POST", "/api/calendar", b),
    delCalendar: (id) => req("DELETE", `/api/calendar/${id}`),

    platformRules: () => req("GET", "/api/settings/platform-rules"),
    styleRules: () => req("GET", "/api/settings/style-rules"),
    createStyleRule: (b) => req("POST", "/api/settings/style-rules", b),
    toggleStyleRule: (id) => req("POST", `/api/settings/style-rules/${id}/toggle`),
    delStyleRule: (id) => req("DELETE", `/api/settings/style-rules/${id}`),
    apCheck: (text) => req("POST", "/api/settings/ap-check", { text }),
    snippets: (kind) => req("GET", "/api/settings/snippets" + (kind ? `?kind=${kind}` : "")),
    createSnippet: (b) => req("POST", "/api/settings/snippets", b),
    delSnippet: (id) => req("DELETE", `/api/settings/snippets/${id}`),
    appSettings: () => req("GET", "/api/settings/app"),
    setAppSetting: (b) => req("PUT", "/api/settings/app", b),
  };
})();

const API = '';  // Same origin

function app() {
  return {
    // State
    view: 'pipeline',
    clients: [],
    selectedClientId: null,
    weightPreset: '60/40',
    filterTier: '',
    sortBy: 'matchmaker_score',
    sortDir: 'desc',
    pipelineEntries: [],
    summary: { total: 0, hot: 0, warm: 0, monitor: 0, pass_count: 0, unscored: 0 },
    activityLog: [],
    scoring: false,

    // Detail panel
    detailOpen: false,
    detailEntry: null,
    detailTab: 'scoring',
    detailCriterionScores: [],
    detailRelationships: [],
    detailIntro: null,
    detailActivity: [],
    generatingIntro: false,

    // Import modal
    showImportModal: false,
    importText: '',
    importing: false,

    // Quick add
    quickAddName: '',

    // Selection
    selectedEntries: [],

    async init() {
      await this.loadClients();
      if (this.clients.length > 0) {
        this.selectedClientId = this.clients[0].id;
        await this.loadPipeline();
      }
      await this.loadActivity();
    },

    // ---- Data Loading ----

    async loadClients() {
      const res = await fetch(`${API}/api/clients`);
      this.clients = await res.json();
    },

    async loadPipeline() {
      if (!this.selectedClientId) return;

      let url = `${API}/api/pipeline/${this.selectedClientId}?sort_by=${this.sortBy}&sort_dir=${this.sortDir}`;
      if (this.filterTier) url += `&tier=${this.filterTier}`;

      const res = await fetch(url);
      this.pipelineEntries = await res.json();

      // Clear selections that no longer exist
      const ids = new Set(this.pipelineEntries.map(e => e.id));
      this.selectedEntries = this.selectedEntries.filter(id => ids.has(id));

      // Load summary
      const sumRes = await fetch(`${API}/api/pipeline/${this.selectedClientId}/summary`);
      this.summary = await sumRes.json();
    },

    async loadActivity() {
      let url = `${API}/api/activity?limit=50`;
      if (this.selectedClientId) url += `&client_id=${this.selectedClientId}`;
      const res = await fetch(url);
      this.activityLog = await res.json();
    },

    // ---- Quick Add ----

    async quickAdd() {
      const name = this.quickAddName.trim();
      if (!name || !this.selectedClientId) return;

      const res = await fetch(
        `${API}/api/pipeline/quick-add?client_id=${this.selectedClientId}&company_name=${encodeURIComponent(name)}`,
        { method: 'POST' }
      );

      if (res.ok) {
        this.quickAddName = '';
        await this.loadPipeline();
        await this.loadActivity();
      }
    },

    // ---- Remove ----

    async removeEntry(entry) {
      if (!entry) return;
      if (!confirm(`Remove ${entry.prospect_name} from the pipeline?`)) return;

      await fetch(`${API}/api/pipeline/${entry.id}`, { method: 'DELETE' });
      await this.loadPipeline();
      await this.loadActivity();
    },

    async removeSelected() {
      if (this.selectedEntries.length === 0) return;
      const count = this.selectedEntries.length;
      if (!confirm(`Remove ${count} company(ies) from the pipeline?`)) return;

      // Remove one by one (simple, reliable)
      for (const id of this.selectedEntries) {
        await fetch(`${API}/api/pipeline/${id}`, { method: 'DELETE' });
      }
      this.selectedEntries = [];
      await this.loadPipeline();
      await this.loadActivity();
    },

    // ---- Selection ----

    toggleSelectAll(event) {
      if (event.target.checked) {
        this.selectedEntries = this.pipelineEntries.map(e => e.id);
      } else {
        this.selectedEntries = [];
      }
    },

    // ---- Sorting ----

    toggleSort(field) {
      if (this.sortBy === field) {
        this.sortDir = this.sortDir === 'desc' ? 'asc' : 'desc';
      } else {
        this.sortBy = field;
        this.sortDir = 'desc';
      }
      this.loadPipeline();
    },

    // ---- Weights ----

    async applyWeights() {
      const map = {
        '60/40': { pmf_weight: 0.6, rs_weight: 0.4 },
        '80/20': { pmf_weight: 0.8, rs_weight: 0.2 },
        '50/50': { pmf_weight: 0.5, rs_weight: 0.5 },
        '30/70': { pmf_weight: 0.3, rs_weight: 0.7 },
      };
      const weights = map[this.weightPreset] || map['60/40'];

      await fetch(`${API}/api/pipeline/${this.selectedClientId}/weights`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(weights),
      });

      await this.loadPipeline();
      await this.loadActivity();
    },

    // ---- Scoring ----

    async scoreAll() {
      if (!this.selectedClientId) return;
      this.scoring = true;

      try {
        await fetch(`${API}/api/pipeline/${this.selectedClientId}/score-all`, { method: 'POST' });
        await this.loadPipeline();
        await this.loadActivity();
      } finally {
        this.scoring = false;
      }
    },

    // ---- Detail Panel ----

    async openDetail(entry) {
      this.detailEntry = entry;
      this.detailTab = 'scoring';
      this.detailOpen = true;
      this.detailIntro = null;

      // Load criterion scores
      const scoresRes = await fetch(`${API}/api/pipeline/${entry.id}/scores`);
      this.detailCriterionScores = await scoresRes.json();

      // Load relationships
      const relRes = await fetch(`${API}/api/relationships/${entry.prospect_id}`);
      this.detailRelationships = await relRes.json();

      // Load intro if exists
      try {
        const introRes = await fetch(`${API}/api/intros/${entry.id}`);
        if (introRes.ok) {
          this.detailIntro = await introRes.json();
        }
      } catch (e) { /* no intro yet */ }

      // Load activity
      const actRes = await fetch(`${API}/api/activity/${entry.id}`);
      this.detailActivity = await actRes.json();
    },

    // ---- Intro Generation ----

    async generateIntro() {
      if (!this.detailEntry) return;
      this.generatingIntro = true;

      try {
        const res = await fetch(`${API}/api/intros/generate/${this.detailEntry.id}`, { method: 'POST' });
        if (res.ok) {
          this.detailIntro = await res.json();
        }
      } finally {
        this.generatingIntro = false;
      }
    },

    async markIntroSent() {
      if (!this.detailIntro) return;
      await fetch(`${API}/api/intros/${this.detailIntro.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'sent' }),
      });
      this.detailIntro.status = 'sent';
      await this.loadPipeline();
      await this.loadActivity();
    },

    // ---- Import ----

    async importCompanies() {
      if (!this.importText.trim() || !this.selectedClientId) return;
      this.importing = true;

      try {
        const names = this.importText.split('\n').map(n => n.trim()).filter(n => n);

        // Create prospects
        const prospectRes = await fetch(`${API}/api/prospects/bulk`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ names }),
        });
        const prospects = await prospectRes.json();

        // Add to pipeline
        await fetch(`${API}/api/pipeline/bulk`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            client_id: parseInt(this.selectedClientId),
            prospect_ids: prospects.map(p => p.id),
            source: 'Manual import',
          }),
        });

        this.showImportModal = false;
        this.importText = '';
        await this.loadPipeline();
        await this.loadActivity();
      } finally {
        this.importing = false;
      }
    },

    // ---- Helpers ----

    rsDots(score) {
      let html = '';
      for (let i = 1; i <= 5; i++) {
        if (i <= score) {
          html += '<span class="dot-filled">&#9679;</span>';
        } else {
          html += '<span class="dot-empty">&#9679;</span>';
        }
      }
      return html;
    },

    formatDate(dateStr) {
      if (!dateStr) return '';
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
    },
  };
}

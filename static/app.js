const API = '';

function app() {
  return {
    view: 'pipeline',
    clients: [],
    selectedClientId: null,
    activeClient: null,
    weightPreset: '60/40',
    pmfWeightPct: 60,
    rsWeightPct: 40,
    filterTier: '',
    pipelineSearch: '',

    // Score delta tracking: previous Matchmaker snapshot per client_id → {prospect_id: score}
    _scoreBaseline: {},

    // Agents view
    agents: [],
    agentRunning: null,
    hsQuery: '',
    hsImportRunning: false,
    hsImportResult: null,
    syncingPipelines: false,
    syncResult: null,

    // Table display preferences (persisted to localStorage)
    tableDensity: 'comfortable',      // 'comfortable' | 'compact'
    columnVisibility: {               // default: everything visible
      type: true, pmf: true, rs: true, matchmaker: true,
      fric: true, intent: true, tier: true, best_contact: true, status: true,
    },
    showColumnMenu: false,
    sortBy: 'matchmaker_score',
    sortDir: 'desc',
    pipelineEntries: [],
    summary: { total: 0, hot: 0, warm: 0, monitor: 0, pass_count: 0, unscored: 0 },
    activityLog: [],
    scoring: false,

    // Criteria library
    criteria: [],           // Active criteria for current client
    allClientCriteria: [],  // All criteria (active + inactive) for current client
    libraryGroups: [],      // Full library grouped
    criteriaOpen: false,
    newCriterionName: '',
    totalLibraryCount: 0,
    activeCriteriaCount: 0,

    // Sources
    sources: [
      { key: 'gmail', label: 'Gmail', enabled: true, configured: false },
      { key: 'hubspot', label: 'HubSpot', enabled: true, configured: false },
      { key: 'calendar', label: 'Google Calendar', enabled: true, configured: false },
      { key: 'conference', label: 'Conference Lists', enabled: true, configured: true },
      { key: 'relmap', label: 'Relationship Map', enabled: true, configured: true },
    ],

    // Detail panel
    detailOpen: false,
    detailEntry: null,
    detailTab: 'profile',
    detailMenuOpen: false,
    detailBreakdown: null,
    detailCriterionScores: [],
    detailRelationships: [],
    detailIntro: null,
    detailActivity: [],
    detailIntroObjections: [],
    generatingIntro: false,
    promotingClient: false,
    introContactName: '',
    introDirty: false,
    introSaving: false,
    introPendingActionId: null,
    _introSaveTimer: null,
    _introPollTimer: null,

    // Client search modal
    showNewClientModal: false,
    clientSearchQuery: '',
    clientSearching: false,
    hubspotResults: [],
    apolloResults: [],
    showManualEntry: false,
    manualClientName: '',
    manualClientDomain: '',
    manualClientDesc: '',
    researchingClient: false,
    clientResearchStatus: '',
    _searchDebounce: null,

    // Import modal
    showImportModal: false,
    importText: '',
    importing: false,

    // Quick add + selection
    quickAddName: '',
    selectedEntries: [],

    // Client dropdown (grouped)
    selectedClientOption: '',
    availableProspects: [],
    lensOptions: [],
    clientCriteriaCounts: {},

    // Scoring presets
    scoringPresets: [],
    selectedPreset: '',
    presetDescription: '',
    advancedWeights: false,

    // Unified tooltip system — ONE popup, delegation-based triggering.
    // Use data-tt="key" in HTML. Content registered in TOOLTIP_CONTENT below.
    tt: { visible: false, x: 0, y: 0, content: null },
    _ttTimer: null,
    _ttInstalled: false,

    // Score breakdown hover popup
    breakdown: null,
    breakdownVisible: false,
    breakdownX: 0,
    breakdownY: 0,
    _breakdownCache: {},
    _breakdownTimer: null,
    promotingFromDropdown: false,
    promotingStatus: '',
    clientDropdownOpen: false,
    loadingClientName: '',   // Name of the client/prospect being loaded (for spinner)
    loadingClientType: '',   // 'client' | 'prospect' (for different messaging)

    // Behavior profile (detail panel)
    behaviorForm: { sales_motion: '', partner_model: '', decision_speed: '', culture: '', customer_segment: '', partnership_history: '', assessed_by: '' },

    // Intent signals (detail panel)
    detailIntentSignals: [],
    intentForm: { signal_type: 'hiring', signal_detail: '', urgency: 'moderate' },

    // Identity filters
    filtersOpen: false,
    hasFilters: false,
    filterConfig: { allowed_business_models: [], allowed_stages: [], min_employees: null, max_employees: null, excluded_verticals_text: '', notes: '' },
    filterPreview: null,
    filterPreviewLoading: false,
    _filterPreviewTimer: null,

    // Business profile
    businessProfile: null,
    deepResearching: false,
    enriching: false,
    inferringBehavior: false,
    currentProspectType: '',
    updatingType: false,

    // Post-creation Deep Research offer dialog
    showDeepResearchOffer: false,
    deepResearchOfferName: '',

    // Client refresh menu
    showRefreshMenu: false,
    refreshing: false,
    refreshStatus: '',
    lastRefreshInfo: '',
    _initialLoad: true,  // suppress popup on first page load

    // Notifications + Cost Gate
    unreadCount: 0,
    pendingActions: 0,
    showNotificationsPanel: false,
    pendingActionsList: [],
    recentNotifications: [],
    _notifInterval: null,

    // Toast
    toastMessage: '',
    _toastTimeout: null,

    async init() {
      // Restore table prefs
      try {
        const d = localStorage.getItem('bd_table_density');
        if (d) this.tableDensity = d;
        const c = localStorage.getItem('bd_column_visibility');
        if (c) this.columnVisibility = { ...this.columnVisibility, ...JSON.parse(c) };
      } catch (e) {}

      // Global keyboard shortcuts
      window.addEventListener('keydown', (e) => this._handleGlobalKey(e));

      // Unified tooltip system (delegation-based)
      this._initTooltips();

      await this.loadSourceStatus();
      await this.loadScoringPresets();
      await this.loadClients();
      await this.loadAvailableProspects();
      if (this.clients.length > 0) {
        this.selectedClientId = this.clients[0].id;
        this.selectedClientOption = 'client:' + this.clients[0].id;
        await this.onClientChange();
      }
      await this.loadActivity();
      await this.loadNotifications();
      // Poll for new notifications every 30 seconds
      this._notifInterval = setInterval(() => this.pollNotifications(), 30000);
      // Mark initial load complete so refresh menu appears on subsequent selections
      this._initialLoad = false;
    },

    // ---- Notifications + Cost Gate ----

    async loadNotifications() {
      try {
        const countRes = await fetch(`${API}/api/notifications/count`);
        const counts = await countRes.json();
        this.unreadCount = counts.unread;
        this.pendingActions = counts.pending_actions;

        if (this.pendingActions > 0) {
          const pendRes = await fetch(`${API}/api/notifications/pending`);
          this.pendingActionsList = await pendRes.json();
        } else {
          this.pendingActionsList = [];
        }

        const notifRes = await fetch(`${API}/api/notifications/?limit=10`);
        this.recentNotifications = await notifRes.json();
      } catch (e) {}
    },

    async pollNotifications() {
      try {
        const countRes = await fetch(`${API}/api/notifications/count`);
        const counts = await countRes.json();
        if (counts.unread !== this.unreadCount || counts.pending_actions !== this.pendingActions) {
          this.unreadCount = counts.unread;
          this.pendingActions = counts.pending_actions;
          await this.loadNotifications();
        }
      } catch (e) {}
    },

    async approveAction(actionId) {
      const res = await fetch(`${API}/api/notifications/pending/${actionId}/approve`, { method: 'POST' });
      const data = await res.json();
      await this.loadNotifications();
      await this.loadPipeline();
      this.showToast('Action approved and executed.');
    },

    async rejectAction(actionId) {
      await fetch(`${API}/api/notifications/pending/${actionId}/reject`, { method: 'POST' });
      await this.loadNotifications();
      this.showToast('Action skipped.');
    },

    async markAllRead() {
      await fetch(`${API}/api/notifications/read-all`, { method: 'PUT' });
      this.unreadCount = 0;
      this.showNotificationsPanel = false;
      await this.loadNotifications();
    },

    // ---- Source Status ----

    async loadSourceStatus() {
      try {
        const res = await fetch(`${API}/api/sources/status`);
        if (!res.ok) return;
        const status = await res.json();
        // Map backend keys to the sources array
        this.sources = this.sources.map(s => ({
          ...s,
          configured: status[s.key]?.configured || false,
        }));
      } catch (e) { /* keep defaults */ }
    },

    // ---- Toast ----

    showToast(message, duration = 4000) {
      this.toastMessage = message;
      clearTimeout(this._toastTimeout);
      this._toastTimeout = setTimeout(() => { this.toastMessage = ''; }, duration);
    },

    // ---- Client Layer ----

    async loadClients() {
      const res = await fetch(`${API}/api/clients`);
      this.clients = await res.json();
      // Load criteria counts
      try {
        const ccRes = await fetch(`${API}/api/clients/criteria-counts`);
        this.clientCriteriaCounts = await ccRes.json();
      } catch (e) { this.clientCriteriaCounts = {}; }
      // Also refresh the unified lens options (every company in the pool)
      await this.loadLensOptions();
    },

    async loadAvailableProspects() {
      const res = await fetch(`${API}/api/prospects/available-as-clients`);
      this.availableProspects = await res.json();
    },

    async loadLensOptions() {
      try {
        const res = await fetch(`${API}/api/clients/lens-options`);
        this.lensOptions = await res.json();
      } catch (e) { this.lensOptions = []; }
    },

    async selectLens(opt) {
      this.clientDropdownOpen = false;
      if (!opt) return;

      if (opt.has_client_record) {
        // Already a client — load directly
        this.loadingClientName = opt.name;
        this.loadingClientType = 'client';
        try {
          this.selectedClientId = opt.client_id;
          this.selectedClientOption = 'client:' + opt.client_id;
          await this.onClientChange();
          if (!this._initialLoad) { await this._computeLastRefreshInfo(); }
        } finally {
          this.loadingClientName = '';
          this.loadingClientType = '';
        }
        return;
      }

      // No client record yet — auto-promote this prospect into a lens (free, instant)
      this.loadingClientName = opt.name;
      this.loadingClientType = 'prospect';
      this.promotingFromDropdown = true;
      this.promotingStatus = `Setting up ${opt.name} as a lens (free, instant)...`;
      try {
        const res = await fetch(`${API}/api/clients/promote/${opt.prospect_id}`, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
          await this.loadClients();
          this.selectedClientId = data.client.id;
          this.selectedClientOption = 'client:' + data.client.id;
          await this.onClientChange();
        } else {
          this.showToast(`Failed: ${data.detail || 'Unknown error'}`);
        }
      } catch (e) {
        this.showToast(`Failed: ${e.message}`);
      } finally {
        this.promotingFromDropdown = false;
        this.promotingStatus = '';
        this.loadingClientName = '';
        this.loadingClientType = '';
      }
    },

    async onClientSelect() {
      const val = this.selectedClientOption;
      if (!val) return;

      const [type, id] = val.split(':');

      if (type === 'client') {
        // Existing client, load directly - show immediate visual feedback
        const clickedClient = this.clients.find(c => c.id === parseInt(id));
        this.loadingClientName = clickedClient?.name || 'client';
        this.loadingClientType = 'client';
        try {
          this.selectedClientId = parseInt(id);
          await this.onClientChange();
          // Auto-popup removed - user clicks the refresh button when they want to refresh
          if (!this._initialLoad) {
            await this._computeLastRefreshInfo();
          }
        } finally {
          this.loadingClientName = '';
          this.loadingClientType = '';
        }
      } else if (type === 'prospect') {
        // Promote prospect to client - this takes 30-40 seconds
        const clickedProspect = this.availableProspects.find(p => p.id === parseInt(id));
        this.loadingClientName = clickedProspect?.name || 'prospect';
        this.loadingClientType = 'prospect';
        this.promotingFromDropdown = true;
        this.promotingStatus = `Adding ${clickedProspect?.name || 'company'} as client (free, instant)...`;

        try {
          const res = await fetch(`${API}/api/clients/promote/${id}`, { method: 'POST' });
          const data = await res.json();

          if (res.ok) {
            await this.loadClients();
            await this.loadAvailableProspects();
            this.selectedClientId = data.client.id;
            this.selectedClientOption = 'client:' + data.client.id;
            await this.onClientChange();
            // Offer Deep Research upgrade via clickable dialog
            this.deepResearchOfferName = data.client.name;
            this.showDeepResearchOffer = true;
          } else {
            this.promotingStatus = 'Error: ' + (data.detail || 'Failed');
            if (this.selectedClientId) {
              this.selectedClientOption = 'client:' + this.selectedClientId;
            }
          }
        } catch (e) {
          this.promotingStatus = 'Error: ' + e.message;
          if (this.selectedClientId) {
            this.selectedClientOption = 'client:' + this.selectedClientId;
          }
        } finally {
          this.promotingFromDropdown = false;
          this.promotingStatus = '';
          this.loadingClientName = '';
          this.loadingClientType = '';
        }
      }
    },

    async onClientChange() {
      if (!this.selectedClientId) return;
      const res = await fetch(`${API}/api/clients/${this.selectedClientId}`);
      this.activeClient = await res.json();
      await this.loadCriteria();
      await this.loadFilters();
      await this.loadPipeline();
    },

    async toggleClientActive() {
      if (!this.selectedClientId) return;
      const res = await fetch(`${API}/api/clients/${this.selectedClientId}/toggle-active`, { method: 'PUT' });
      const data = await res.json();
      this.activeClient.active = data.active;
      await this.loadClients();
      await this.loadPipeline();
      await this.loadActivity();
      this.showToast(`${data.name} marked as ${data.active ? 'ACTIVE' : 'INACTIVE'}.`);
    },

    async deleteClient() {
      if (!this.selectedClientId || !this.activeClient) return;
      const name = this.activeClient.name;
      if (!confirm(`Delete ${name} as a client?\n\nThey will stay in the system as a prospect and continue to appear in other clients' pipelines. This only removes their client role, criteria, and identity filter.`)) return;

      const res = await fetch(`${API}/api/clients/${this.selectedClientId}`, { method: 'DELETE' });
      if (!res.ok) { this.showToast(`Delete failed: ${res.status}`); return; }

      await this.loadClients();
      // Switch to first remaining client, if any
      this.selectedClientId = this.clients.length ? this.clients[0].id : null;
      if (this.selectedClientId) {
        await this.loadClientDetail();
      } else {
        this.activeClient = null;
        this.pipelineEntries = [];
      }
      await this.loadActivity();
      this.showToast(`${name} removed as client. Still tracked as prospect.`);
    },

    async deleteCompanyEverywhere() {
      if (!this.selectedClientId || !this.activeClient) return;
      const name = this.activeClient.name;
      if (!confirm(`NUCLEAR DELETE — ${name}\n\nThis wipes ${name} from the entire system:\n• Client record\n• Prospect record\n• Every pipeline entry across all clients\n• Business profile, behavior profile, relationships, intent signals\n\nThis cannot be undone. Continue?`)) return;
      if (!confirm(`Final confirmation. Permanently delete ${name} everywhere?`)) return;

      const res = await fetch(`${API}/api/clients/${this.selectedClientId}/cascade-everywhere`, { method: 'DELETE' });
      if (!res.ok) { this.showToast(`Delete failed: ${res.status}`); return; }

      await this.loadClients();
      this.selectedClientId = this.clients.length ? this.clients[0].id : null;
      if (this.selectedClientId) {
        await this.loadClientDetail();
      } else {
        this.activeClient = null;
        this.pipelineEntries = [];
      }
      await this.loadActivity();
      this.showToast(`${name} deleted everywhere.`);
    },

    async deleteProspectEverywhere(entry) {
      if (!entry) return;
      const name = entry.prospect_name;
      if (!confirm(`NUCLEAR DELETE — ${name}\n\nWipes ${name} from the entire system (every pipeline, profile, and client record if any). This cannot be undone. Continue?`)) return;

      const res = await fetch(`${API}/api/prospects/${entry.prospect_id}/cascade-everywhere`, { method: 'DELETE' });
      if (!res.ok) { this.showToast(`Delete failed: ${res.status}`); return; }

      await this.loadClients();
      await this.loadPipeline();
      await this.loadActivity();
      this.detailOpen = false;
      this.showToast(`${name} deleted everywhere.`);
    },

    // ---- Client Search (Path 1) ----

    debounceClientSearch() {
      clearTimeout(this._searchDebounce);
      this.showManualEntry = false;
      if (this.clientSearchQuery.length < 2) {
        this.hubspotResults = [];
        this.apolloResults = [];
        return;
      }
      this._searchDebounce = setTimeout(() => this.runClientSearch(), 300);
    },

    async runClientSearch() {
      this.clientSearching = true;
      this.hubspotResults = [];
      this.apolloResults = [];

      try {
        const res = await fetch(`${API}/api/clients/search?q=${encodeURIComponent(this.clientSearchQuery)}`);
        const data = await res.json();

        if (data.hubspot?.available) {
          this.hubspotResults = data.hubspot.results || [];
        }
        if (data.apollo?.available) {
          this.apolloResults = data.apollo.results || [];
        }

        // If both unavailable and no results, show manual entry
        if (!data.hubspot?.available && !data.apollo?.available) {
          this.showManualEntry = true;
          this.manualClientName = this.clientSearchQuery;
        }
      } catch (e) {
        console.error('Client search error:', e);
        this.showManualEntry = true;
        this.manualClientName = this.clientSearchQuery;
      } finally {
        this.clientSearching = false;
      }
    },

    async selectSearchResult(result) {
      this.researchingClient = true;
      this.clientResearchStatus = `Creating ${result.name}... Researching profile and generating scoring criteria.`;

      try {
        const params = new URLSearchParams({
          name: result.name,
          source: result.source,
          domain: result.domain || '',
          description: result.description || '',
          city: result.city || '',
          state: result.state || '',
          industry: result.industry || '',
          employees: result.employees ? String(result.employees) : '',
          revenue: result.revenue || '',
          phone: result.phone || '',
          hubspot_id: result.hubspot_id || '',
        });

        const res = await fetch(`${API}/api/clients/from-source?${params}`, { method: 'POST' });
        const data = await res.json();

        if (res.ok) {
          await this.loadClients();
          await this.loadAvailableProspects();
          this.selectedClientId = data.client.id;
          this.selectedClientOption = 'client:' + data.client.id;
          await this.onClientChange();
          this.showNewClientModal = false;
          this.resetClientSearch();
          this.showToast(`${data.client.name} added as client. ${data.criteria.length} criteria generated.`);
        } else {
          this.clientResearchStatus = 'Error: ' + (data.detail || 'Failed to create client');
        }
      } catch (e) {
        this.clientResearchStatus = 'Error: ' + e.message;
      } finally {
        this.researchingClient = false;
      }
    },

    // ---- Manual Entry (Path 3) ----

    async createClientManual() {
      const name = this.manualClientName.trim();
      if (!name) return;
      this.researchingClient = true;
      this.clientResearchStatus = `Creating ${name}... Researching profile and generating scoring criteria.`;

      try {
        const params = new URLSearchParams({
          name,
          source: 'manual',
          domain: this.manualClientDomain.trim(),
          description: this.manualClientDesc.trim(),
        });

        const res = await fetch(`${API}/api/clients/from-source?${params}`, { method: 'POST' });
        const data = await res.json();

        if (res.ok) {
          await this.loadClients();
          await this.loadAvailableProspects();
          this.selectedClientId = data.client.id;
          this.selectedClientOption = 'client:' + data.client.id;
          await this.onClientChange();
          this.showNewClientModal = false;
          this.resetClientSearch();
          this.showToast(`${data.client.name} added as client. ${data.criteria.length} criteria generated.`);
        } else {
          this.clientResearchStatus = 'Error: ' + (data.detail || 'Failed');
        }
      } catch (e) {
        this.clientResearchStatus = 'Error: ' + e.message;
      } finally {
        this.researchingClient = false;
      }
    },

    resetClientSearch() {
      this.clientSearchQuery = '';
      this.hubspotResults = [];
      this.apolloResults = [];
      this.showManualEntry = false;
      this.manualClientName = '';
      this.manualClientDomain = '';
      this.manualClientDesc = '';
      this.clientResearchStatus = '';
    },

    // ---- Promote Prospect to Client (Path 2) ----

    isProspectAlreadyClient() {
      if (!this.detailEntry) return true;
      return this.clients.some(c => c.name.toLowerCase() === (this.detailEntry.prospect_name || '').toLowerCase());
    },

    async promoteToClient() {
      if (!this.detailEntry) return;
      if (!confirm(`Add ${this.detailEntry.prospect_name} as a client? This will generate a profile and scoring criteria.`)) return;

      this.promotingClient = true;
      try {
        const res = await fetch(`${API}/api/clients/promote/${this.detailEntry.prospect_id}`, { method: 'POST' });
        const data = await res.json();

        if (res.ok) {
          await this.loadClients();
          await this.loadAvailableProspects();
          this.showToast(`${data.client.name} is now a client. You can score pipelines for them.`);
        } else {
          alert('Error: ' + (data.detail || 'Failed to promote'));
        }
      } catch (e) {
        alert('Error: ' + e.message);
      } finally {
        this.promotingClient = false;
      }
    },

    // ---- Criteria Library ----

    async loadCriteria() {
      if (!this.selectedClientId) return;
      // Load active criteria
      const res = await fetch(`${API}/api/clients/${this.selectedClientId}/criteria`);
      this.criteria = await res.json();
      this.activeCriteriaCount = this.criteria.filter(c => c.active !== false).length;

      // Load all criteria (including inactive)
      const allRes = await fetch(`${API}/api/clients/${this.selectedClientId}/criteria?include_inactive=true`);
      this.allClientCriteria = await allRes.json();

      // Load library
      const libRes = await fetch(`${API}/api/clients/library/all`);
      this.libraryGroups = await libRes.json();
      this.libraryGroups.forEach(g => g._open = false);
      this.totalLibraryCount = this.libraryGroups.reduce((sum, g) => sum + g.criteria.length, 0);
    },

    // ===== Unified Tooltip System =====
    // ONE popup, delegation-based. Any element with `data-tt="key"` shows a tooltip.
    // For criterion tiles, use `data-tt="criterion"` + `data-tt-id="<library_id>"`.

    _ttRegistry() {
      return {
        // Pipeline column headers
        col_matchmaker: { title: 'Matchmaker Score', body: 'Final 0-100 score. Combines PMF (fit) and RS (relationship), then multiplies by Friction and Intent. Higher is better.', scale: [['70+','Hot'],['50-69','Warm'],['30-49','Monitor'],['< 30','Pass']] },
        col_pmf: { title: 'PMF · Product-Market Fit', body: 'How well this prospect matches your lens on the criteria you enabled. Averaged from all active criterion scores, weighted by importance, normalized to 0-100.' },
        col_rs: { title: 'RS · Relationship Strength', body: 'How strong your existing relationship is with this prospect, 0-5. Built from email history, calendar meetings, conference overlaps, CRM activity, and manual notes.', scale: [['5','Inner circle'],['4','Strong'],['3','Warm'],['2','Light'],['1','Aware'],['0','Cold']] },
        col_fric: { title: 'Fric · Friction Coefficient', body: 'How easily you can do business with them, 0.7-1.0. Compares behavior profiles; lower means more friction.' },
        col_intent: { title: 'Intent · Buying Signal Multiplier', body: 'Whether the prospect is in-market, 0.8-1.5×. Built from hiring, funding, partnership announcements, product launches, strategic statements.' },
        col_tier: { title: 'Tier', body: 'Bucket based on Matchmaker Score. Drives outreach priority.', scale: [['Hot','70+ priority'],['Warm','50-69 secondary'],['Monitor','30-49 track'],['Pass','< 30 skip'],['Filtered','blocked by identity filter']] },
        col_company: { title: 'Company', body: 'The prospect being evaluated against the selected lens. Click to open the detail panel.' },
        col_type: { title: 'Type', body: 'Company category. Drives heuristic scoring and default behavior profile.' },
        // Criteria groups
        group_market: { title: 'Market Fit', body: 'Do they serve overlapping customers? Covers geography, buyer personas, customer segments, insurance lines.' },
        group_product: { title: 'Product & Technology', body: 'Can we build something together? Covers complementarity, APIs, platform compatibility, digital capabilities.' },
        group_business: { title: 'Business Dynamics', body: 'Will the deal structure work? Covers distribution focus, revenue model, partnership history, regulatory coverage.' },
        group_relationship: { title: 'Relationship & Timing', body: 'Can you execute right now? Covers decision-maker access, sales cycle, strategic priority, event proximity.' },
        // Tier chips
        tier_hot: { title: 'Hot · 70+', body: 'Strong fit or relationship. Priority for outreach this week. Worth generating an intro for.' },
        tier_warm: { title: 'Warm · 50-69', body: 'Solid candidate. Secondary priority. Often one better signal away from Hot.' },
        tier_monitor: { title: 'Monitor · 30-49', body: 'Track for change. Do not pursue. If a material event happens, they could move up.' },
        tier_pass: { title: 'Pass · Below 30', body: 'Skip for now. Poor fit on market or product dimensions. Revisit only if something changes.' },
        tier_filtered: { title: 'Filtered', body: 'Excluded by a Layer 1 identity filter before scoring. Edit the filter to include them.' },
        // Layer tiles (richer, still rendered by the same popup)
        layer1: { title: 'Layer 1: Client', subtitle: 'The lens', what: 'Pick any company to use as the lens. Their profile becomes the perspective the pipeline is scored against.', why: 'Scoring is directional. Same prospect scored against Tivly vs Circle AI produces different results — because the criteria and context flip.', how: 'Click the dropdown. Active clients show first with a green ✓. Any company in the system is selectable. New lens = auto-generates criteria + rescores everything.', effect: 'Changes the entire pipeline below. New lens = new scores, new ranks, new tiers.' },
        layer2: { title: 'Layer 2: Data Sources', subtitle: 'Relationship evidence', what: 'Toggles which external sources feed the Relationship Score (RS). Sources include Gmail, Calendar, HubSpot, conference DB, internal notes.', why: 'RS is the second half of Matchmaker. Turning sources on/off changes what counts as relationship evidence.', how: 'Check a source to include it. Green "Active" means configured and returning data. Gray "Stub" means the integration is scaffolded but not connected.', effect: 'Moves RS scores directly, which flows into Matchmaker.' },
        layer3: { title: 'Layer 3: Scoring Weights', subtitle: 'Fit vs relationship balance', what: 'Controls how much of the Matchmaker score comes from PMF (fit via criteria) vs RS (relationship strength).', why: 'Cold prospecting leans on PMF. Network-first strategies lean on RS. Different deals need different balances.', how: 'Pick a preset (60/40 default, 80/20 cold, 50/50 balanced, 30/70 network-first) or drag sliders for custom mix.', effect: 'Rebalances every Matchmaker score in the pipeline instantly.' },
      };
    },

    _ttLookupContent(el) {
      const key = el.getAttribute('data-tt');
      if (!key) return null;
      if (key === 'criterion') {
        // Dynamic: look up library entry by id
        const id = parseInt(el.getAttribute('data-tt-id'), 10);
        if (!id) return null;
        for (const g of (this.libraryGroups || [])) {
          for (const lib of (g.criteria || [])) {
            if (lib.library_id === id) {
              return {
                title: lib.name,
                subtitle: g.group_name,
                body: lib.description,
                why: lib.why_it_matters,
                scoreScale: true,
              };
            }
          }
        }
        return null;
      }
      return this._ttRegistry()[key] || null;
    },

    _ttPosition(el, width = 320) {
      const rect = el.getBoundingClientRect();
      let x = rect.left + rect.width / 2 - width / 2;
      x = Math.max(10, Math.min(window.innerWidth - width - 10, x));
      let y = rect.bottom + 8;
      if (y + 240 > window.innerHeight) {
        y = Math.max(10, rect.top - 250);
      }
      return { x, y };
    },

    _initTooltips() {
      if (this._ttInstalled) return;
      this._ttInstalled = true;

      // Delegation: single pair of listeners for every tooltip in the app
      document.addEventListener('mouseover', (e) => {
        const el = e.target.closest('[data-tt]');
        if (!el) return;
        // Entering the same element we're already showing? No-op.
        if (this._ttCurrentEl === el) return;
        this._ttCurrentEl = el;
        const content = this._ttLookupContent(el);
        if (!content) return;
        clearTimeout(this._ttTimer);
        this._ttTimer = setTimeout(() => {
          const pos = this._ttPosition(el);
          this.tt = { visible: true, x: pos.x, y: pos.y, content };
        }, 350);
      });

      document.addEventListener('mouseout', (e) => {
        const el = e.target.closest('[data-tt]');
        if (!el) return;
        // Moving to a child of the same element? Keep open.
        if (el.contains(e.relatedTarget)) return;
        this._ttCurrentEl = null;
        clearTimeout(this._ttTimer);
        this.tt.visible = false;
      });

      // Safety nets: anything that leaves hover context should clear
      window.addEventListener('scroll', () => { this.tt.visible = false; this._ttCurrentEl = null; }, { passive: true, capture: true });
      window.addEventListener('blur', () => { this.tt.visible = false; this._ttCurrentEl = null; });
      document.addEventListener('visibilitychange', () => { this.tt.visible = false; this._ttCurrentEl = null; });
    },

    weightImpactLabel(weight) {
      const w = parseInt(weight) || 5;
      if (w >= 9) return 'Deal-breaker if missing';
      if (w >= 7) return 'Strong signal';
      if (w >= 5) return 'Meaningful signal';
      if (w >= 3) return 'Nice to have';
      return 'Minor';
    },

    isCriterionActive(libraryId) {
      return this.allClientCriteria.some(c => c.library_id === libraryId && c.active !== false);
    },

    getCriterionWeight(libraryId) {
      const c = this.allClientCriteria.find(c => c.library_id === libraryId);
      return c ? c.weight : 5;
    },

    countActiveInGroup(groupName) {
      return this.allClientCriteria.filter(c => c.group_name === groupName && c.active !== false).length;
    },

    async showBreakdown(entry, event) {
      if (!entry) return;
      this._rememberTipTrigger(event);
      // Position popup to the LEFT of the cell so it doesn't cover the rest of the row
      const rect = event.target.getBoundingClientRect();
      const popupWidth = 360;
      this.breakdownX = Math.max(10, rect.left - popupWidth - 12);
      this.breakdownY = Math.max(10, Math.min(window.innerHeight - 360, rect.top - 40));

      // Show cached version instantly if we have one
      if (this._breakdownCache[entry.id]) {
        this.breakdown = this._breakdownCache[entry.id];
        this.breakdownVisible = true;
        return;
      }

      // Small delay so we don't fire for mouse passing through rows
      clearTimeout(this._breakdownTimer);
      this._breakdownTimer = setTimeout(async () => {
        try {
          const res = await fetch(`${API}/api/pipeline/${entry.id}/breakdown`);
          if (!res.ok) return;
          const data = await res.json();
          this._breakdownCache[entry.id] = data;
          this.breakdown = data;
          this.breakdownVisible = true;
        } catch (e) { /* silent */ }
      }, 150);
    },

    hideBreakdown() {
      clearTimeout(this._breakdownTimer);
      this.breakdownVisible = false;
    },

    // Invalidate breakdown cache after scoring changes
    _invalidateBreakdownCache() {
      this._breakdownCache = {};
    },

    async loadScoringPresets() {
      try {
        const res = await fetch(`${API}/api/clients/presets/list`);
        this.scoringPresets = await res.json();
      } catch (e) { this.scoringPresets = []; }
    },

    async applyPreset() {
      const key = this.selectedPreset;
      if (!key || !this.selectedClientId) {
        this.presetDescription = '';
        return;
      }

      // Update description immediately for user feedback
      if (key === 'custom') {
        this.presetDescription = 'Cleared all criteria. Build your set by toggling tiles below.';
      } else {
        const p = this.scoringPresets.find(x => x.key === key);
        this.presetDescription = p ? p.description : '';
      }

      // Apply on server
      const res = await fetch(`${API}/api/clients/${this.selectedClientId}/presets/apply/${key}`, { method: 'POST' });
      if (!res.ok) {
        this.showToast('Failed to apply preset.');
        return;
      }
      const data = await res.json();
      await this.loadCriteria();
      await this.rescoreAfterToggle();
      this.showToast(key === 'custom'
        ? 'Cleared all criteria. Toggle tiles to build your own.'
        : `Applied ${data.label} — ${data.activated} criteria active.`);
    },

    async toggleLibraryCriterion(libraryId) {
      if (!this.selectedClientId) return;
      await fetch(`${API}/api/clients/${this.selectedClientId}/criteria/toggle/${libraryId}`, { method: 'POST' });
      await this.loadCriteria();
      // Auto-rescore so the toggle immediately reflects in the pipeline
      await this.rescoreAfterToggle();
    },

    async updateLibraryCriterionWeight(libraryId, newWeight) {
      const c = this.allClientCriteria.find(c => c.library_id === libraryId);
      if (!c) return;
      c.weight = parseInt(newWeight);
      await fetch(`${API}/api/clients/${this.selectedClientId}/criteria/${c.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: c.name, description: c.description, why_it_matters: c.why_it_matters, weight: parseInt(newWeight), sort_order: c.sort_order }),
      });
      // Debounce rescore on weight change — fire once 600ms after last slider movement
      clearTimeout(this._weightRescoreTimer);
      this._weightRescoreTimer = setTimeout(() => { this.rescoreAfterToggle(); }, 600);
    },

    async rescoreAfterToggle() {
      this.scoring = true;
      try {
        await fetch(`${API}/api/pipeline/${this.selectedClientId}/score-all`, { method: 'POST' });
        this._invalidateBreakdownCache();
        await this.loadPipeline();
        this.showToast('Pipeline rescored with updated criteria.');
      } finally { this.scoring = false; }
    },

    async updateCriterionWeight(criterion, newWeight) {
      criterion.weight = parseInt(newWeight);
      await fetch(`${API}/api/clients/${this.selectedClientId}/criteria/${criterion.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: criterion.name, description: criterion.description, why_it_matters: criterion.why_it_matters, weight: parseInt(newWeight), sort_order: criterion.sort_order }),
      });
    },

    async addCriterion() {
      const name = this.newCriterionName.trim();
      if (!name || !this.selectedClientId) return;
      await fetch(`${API}/api/clients/${this.selectedClientId}/criteria`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, weight: 5 }),
      });
      this.newCriterionName = '';
      await this.loadCriteria();
    },

    async deleteCriterion(criterion) {
      if (!confirm(`Remove criterion "${criterion.name}"?`)) return;
      await fetch(`${API}/api/clients/${this.selectedClientId}/criteria/${criterion.id}`, { method: 'DELETE' });
      await this.loadCriteria();
    },

    // ---- Weight Layer ----

    async applyWeightPreset() {
      const map = { '60/40': [60, 40], '80/20': [80, 20], '50/50': [50, 50], '30/70': [30, 70], 'custom': [this.pmfWeightPct, this.rsWeightPct] };
      const [pmf, rs] = map[this.weightPreset] || [60, 40];
      this.pmfWeightPct = pmf;
      this.rsWeightPct = rs;
      await this.applyWeights();
    },

    onCustomWeight(event, type) {
      const val = parseInt(event.target.value);
      if (type === 'pmf') { this.pmfWeightPct = val; this.rsWeightPct = 100 - val; }
      else { this.rsWeightPct = val; this.pmfWeightPct = 100 - val; }
      this.weightPreset = 'custom';
      clearTimeout(this._weightDebounce);
      this._weightDebounce = setTimeout(() => this.applyWeights(), 300);
    },

    async applyWeights() {
      if (!this.selectedClientId) return;
      await fetch(`${API}/api/pipeline/${this.selectedClientId}/weights`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pmf_weight: this.pmfWeightPct / 100, rs_weight: this.rsWeightPct / 100 }),
      });
      await this.loadPipeline();
    },

    // ---- Pipeline ----

    async loadPipeline() {
      if (!this.selectedClientId) return;
      let url = `${API}/api/pipeline/${this.selectedClientId}?sort_by=${this.sortBy}&sort_dir=${this.sortDir}`;
      if (this.filterTier) url += `&tier=${this.filterTier}`;
      const res = await fetch(url);
      const newEntries = await res.json();

      // Compute deltas vs the previous snapshot for THIS client
      // Baseline lives per client so switching clients doesn't bleed deltas across.
      const baseline = this._scoreBaseline[this.selectedClientId] || {};
      for (const e of newEntries) {
        const prev = baseline[e.prospect_id];
        const now = e.matchmaker_score;
        if (prev != null && now != null && Math.abs(now - prev) >= 0.1) {
          e._delta = Math.round((now - prev) * 10) / 10;  // one decimal
        } else {
          e._delta = null;
        }
      }
      // Save new snapshot
      const snapshot = {};
      for (const e of newEntries) {
        if (e.matchmaker_score != null) snapshot[e.prospect_id] = e.matchmaker_score;
      }
      this._scoreBaseline[this.selectedClientId] = snapshot;

      this.pipelineEntries = newEntries;
      const ids = new Set(this.pipelineEntries.map(e => e.id));
      this.selectedEntries = this.selectedEntries.filter(id => ids.has(id));
      const sumRes = await fetch(`${API}/api/pipeline/${this.selectedClientId}/summary`);
      this.summary = await sumRes.json();
    },

    // ---- Agents ----

    async loadAgents() {
      try {
        const res = await fetch(`${API}/api/agents/`);
        if (res.ok) {
          const data = await res.json();
          // Preserve the _expanded UI state across reloads if possible
          const prev = Object.fromEntries((this.agents || []).map(j => [j.job_key, j._expanded]));
          this.agents = data.map(j => ({ ...j, _expanded: prev[j.job_key] || false }));
        }
      } catch (e) { this.agents = []; }
    },

    async runAgentNow(jobKey) {
      if (!jobKey) return;
      this.agentRunning = jobKey;
      try {
        const res = await fetch(`${API}/api/agents/${jobKey}/run-now`, { method: 'POST' });
        const data = await res.json();
        if (data.status === 'ok') {
          this.showToast('Agent completed successfully.');
        } else {
          this.showToast(`Agent failed: ${data.error || 'Unknown error'}`);
        }
        await this.loadAgents();
      } finally {
        this.agentRunning = null;
      }
    },

    async syncAllPipelines() {
      this.syncingPipelines = true;
      this.syncResult = null;
      try {
        const res = await fetch(`${API}/api/agents/sync-pipelines`, { method: 'POST' });
        this.syncResult = await res.json();
        this.showToast(`Sync complete. ${this.syncResult.added || 0} pipeline entries added.`);
        if (this.selectedClientId) await this.loadPipeline();
      } finally {
        this.syncingPipelines = false;
      }
    },

    async runHubspotImport() {
      const q = (this.hsQuery || '').trim();
      if (q.length < 2) return;
      this.hsImportRunning = true;
      this.hsImportResult = null;
      try {
        const res = await fetch(`${API}/api/agents/hubspot-import-query`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: q }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
          this.showToast(`Import failed: ${err.detail}`);
          return;
        }
        this.hsImportResult = await res.json();
        const n = this.hsImportResult.imported || 0;
        this.showToast(`Imported ${n} new companies from HubSpot.`);
        // Refresh pipeline if user's on it
        if (this.selectedClientId) await this.loadPipeline();
      } catch (e) {
        this.showToast(`Import error: ${e.message}`);
      } finally {
        this.hsImportRunning = false;
      }
    },

    async toggleAgent(jobKey) {
      if (!jobKey) return;
      try {
        const res = await fetch(`${API}/api/agents/${jobKey}/toggle`, { method: 'POST' });
        if (res.ok) {
          const updated = await res.json();
          this.showToast(`${updated.name} ${updated.enabled ? 'enabled' : 'paused'}.`);
          await this.loadAgents();
        }
      } catch (e) {
        this.showToast('Toggle failed.');
      }
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
      await fetch(`${API}/api/pipeline/quick-add?client_id=${this.selectedClientId}&company_name=${encodeURIComponent(name)}`, { method: 'POST' });
      this.quickAddName = '';
      await this.loadPipeline();
      await this.loadActivity();
      await this.loadAvailableProspects();  // Refresh dropdown so new company appears
      this.showToast(`${name} added to pipeline. Available in Layer 1 dropdown too.`);
    },

    // ---- Remove ----

    async removeEntry(entry) {
      if (!entry) return;
      if (!confirm(`Remove ${entry.prospect_name} from the pipeline?`)) return;
      await fetch(`${API}/api/pipeline/${entry.id}`, { method: 'DELETE' });
      await this.loadPipeline();
      await this.loadActivity();
      this.showToast(`${entry.prospect_name} removed.`);
    },

    async removeSelected() {
      if (this.selectedEntries.length === 0) return;
      const count = this.selectedEntries.length;
      if (!confirm(`Remove ${count} company(ies)?`)) return;
      for (const id of this.selectedEntries) { await fetch(`${API}/api/pipeline/${id}`, { method: 'DELETE' }); }
      this.selectedEntries = [];
      await this.loadPipeline();
      await this.loadActivity();
      this.showToast(`${count} companies removed.`);
    },

    toggleSelectAll(event) {
      this.selectedEntries = event.target.checked ? this.pipelineEntries.map(e => e.id) : [];
    },

    // ---- Sorting ----

    toggleSort(field) {
      if (this.sortBy === field) { this.sortDir = this.sortDir === 'desc' ? 'asc' : 'desc'; }
      else { this.sortBy = field; this.sortDir = 'desc'; }
      this.loadPipeline();
    },

    // ---- Scoring ----

    async scoreAll() {
      if (!this.selectedClientId) return;
      this.scoring = true;
      try {
        await fetch(`${API}/api/pipeline/${this.selectedClientId}/score-all`, { method: 'POST' });
        await this.loadPipeline();
        await this.loadActivity();
      } finally { this.scoring = false; }
    },

    // ---- Detail Panel ----

    async openDetail(entry) {
      this.detailEntry = entry;
      this.detailTab = 'profile';
      this.detailOpen = true;
      this.detailMenuOpen = false;
      this.detailIntro = null;
      this.detailIntentSignals = [];
      this.detailBreakdown = null;
      const [scoresRes, relRes, actRes, breakdownRes] = await Promise.all([
        fetch(`${API}/api/pipeline/${entry.id}/scores`),
        fetch(`${API}/api/relationships/${entry.prospect_id}`),
        fetch(`${API}/api/activity/${entry.id}`),
        fetch(`${API}/api/pipeline/${entry.id}/breakdown`),
      ]);
      this.detailCriterionScores = await scoresRes.json();
      this.detailRelationships = await relRes.json();
      this.detailActivity = await actRes.json();
      if (breakdownRes.ok) this.detailBreakdown = await breakdownRes.json();
      // Load business profile (shown by default now)
      await this.loadBusinessProfile();
      // Load behavior profile
      await this.loadBehavior(entry.prospect_id);
      // Load intent signals
      await this.loadIntentSignals();
      try {
        const introRes = await fetch(`${API}/api/intros/${entry.id}`);
        if (introRes.ok) {
          this.detailIntro = await introRes.json();
          this.introContactName = this.detailIntro?.target_contact || '';
          this.introDirty = false;
          this._parseIntroObjections();
        }
      } catch (e) {}
    },

    plainFormula() {
      const e = this.detailEntry;
      if (!e) return '';
      const pmf = e.pmf_score || 0;
      const rs = e.relationship_score || 0;
      const pmfW = Math.round((e.pmf_weight ?? 0.6) * 100);
      const rsW = Math.round((e.rs_weight ?? 0.4) * 100);
      const fric = e.friction_coefficient ?? 1;
      const intent = e.intent_multiplier ?? 1;
      const parts = [`${pmfW}% Fit (${pmf}) + ${rsW}% Relationship (${rs}/5)`];
      if (fric !== 1) parts.push(`Friction ×${fric}`);
      if (intent !== 1) parts.push(`Intent ×${intent}`);
      return parts.join(' · ');
    },

    async generateIntro() {
      if (!this.detailEntry) return;
      this.generatingIntro = true;
      try {
        const qs = this.introContactName ? `?contact_name=${encodeURIComponent(this.introContactName)}` : '';
        const res = await fetch(`${API}/api/intros/generate/${this.detailEntry.id}${qs}`, { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'pending_approval') {
            // Keep it visible: set pending state on the intro tab + light up notifications
            this.introPendingActionId = data.action_id;
            await this.loadNotifications();
            this.showNotificationsPanel = true;
            this.showToast(`Approval needed. Click "Approve & Run" at the top.`);
            this._startIntroPolling();
          } else {
            this.detailIntro = data;
            this.introDirty = false;
            this._parseIntroObjections();
          }
        }
      } finally { this.generatingIntro = false; }
    },

    _startIntroPolling() {
      // Poll for the intro showing up after approval
      clearInterval(this._introPollTimer);
      const entryId = this.detailEntry?.id;
      if (!entryId) return;
      this._introPollTimer = setInterval(async () => {
        if (!this.detailOpen || this.detailEntry?.id !== entryId) {
          clearInterval(this._introPollTimer);
          return;
        }
        try {
          const r = await fetch(`${API}/api/intros/${entryId}`);
          if (r.ok) {
            this.detailIntro = await r.json();
            this.introContactName = this.detailIntro?.target_contact || '';
            this.introDirty = false;
            this._parseIntroObjections();
            this.introPendingActionId = null;
            clearInterval(this._introPollTimer);
            this.showToast('Intro package ready.');
          }
        } catch (e) { /* keep polling */ }
      }, 3000);
    },

    async cancelPendingIntro() {
      if (!this.introPendingActionId) return;
      try {
        await fetch(`${API}/api/notifications/pending/${this.introPendingActionId}/reject`, { method: 'POST' });
      } catch (e) {}
      this.introPendingActionId = null;
      clearInterval(this._introPollTimer);
      await this.loadNotifications();
      this.showToast('Intro request cancelled.');
    },

    _parseIntroObjections() {
      this.detailIntroObjections = [];
      if (!this.detailIntro?.objections_json) return;
      try {
        const parsed = JSON.parse(this.detailIntro.objections_json);
        if (Array.isArray(parsed)) this.detailIntroObjections = parsed;
      } catch (e) { /* ignore malformed */ }
    },

    async saveIntroEdits() {
      if (!this.detailIntro || !this.introDirty) return;
      clearTimeout(this._introSaveTimer);
      this.introSaving = true;
      try {
        const res = await fetch(`${API}/api/intros/${this.detailIntro.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email_subject: this.detailIntro.email_subject,
            email_body: this.detailIntro.email_body,
          }),
        });
        if (res.ok) this.introDirty = false;
      } finally { this.introSaving = false; }
    },

    voiceWarnings() {
      if (!this.detailIntro) return [];
      const subject = (this.detailIntro.email_subject || '').toLowerCase();
      const body = (this.detailIntro.email_body || '').toLowerCase();
      const combined = subject + ' ' + body;
      const warnings = [];

      // Em dash
      if (combined.includes('—')) warnings.push('Contains em dash (—). Replace with period, comma, or hyphen.');

      // Banned words from CLAUDE.md
      const banned = ['passionate', 'leveraged', 'architected', 'seamless', 'scalable', 'dynamic'];
      const found = banned.filter(w => new RegExp('\\b' + w + '\\b', 'i').test(combined));
      if (found.length) warnings.push('Banned words: ' + found.join(', ') + '. Rewrite without them.');

      // AI-sounding phrases
      const aiPhrases = ['delve into', "it's worth noting", "let's unpack", 'in today\'s landscape', 'it goes without saying', 'at the end of the day'];
      const foundAi = aiPhrases.filter(p => combined.includes(p));
      if (foundAi.length) warnings.push('AI-sounding phrase: "' + foundAi.join('", "') + '". Rewrite in plain voice.');

      // Corporate filler
      return warnings;
    },

    async copyToClipboard(text, label) {
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        this.showToast(`${label || 'Text'} copied to clipboard.`);
      } catch (e) {
        this.showToast('Copy failed. Select the text manually.');
      }
    },

    copyFullEmail() {
      if (!this.detailIntro) return;
      const full = `Subject: ${this.detailIntro.email_subject}\n\n${this.detailIntro.email_body}`;
      this.copyToClipboard(full, 'Full email');
    },

    async markIntroSent() {
      if (!this.detailIntro) return;
      await fetch(`${API}/api/intros/${this.detailIntro.id}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'sent' }),
      });
      this.detailIntro.status = 'sent';
      await this.loadPipeline();
      await this.loadActivity();
      this.showToast('Intro marked as sent.');
    },

    // ---- Import ----

    async importCompanies() {
      if (!this.importText.trim() || !this.selectedClientId) return;
      this.importing = true;
      try {
        const names = this.importText.split('\n').map(n => n.trim()).filter(n => n);
        const prospectRes = await fetch(`${API}/api/prospects/bulk`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ names }),
        });
        const prospects = await prospectRes.json();
        await fetch(`${API}/api/pipeline/bulk`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ client_id: parseInt(this.selectedClientId), prospect_ids: prospects.map(p => p.id), source: 'Manual import' }),
        });
        this.showImportModal = false;
        this.importText = '';
        await this.loadPipeline();
        await this.loadActivity();
        await this.loadAvailableProspects();  // Refresh dropdown to show new companies
        this.showToast(`${names.length} companies imported. Available in Layer 1 dropdown.`);
      } finally { this.importing = false; }
    },

    // ---- Behavior ----

    async loadBehavior(prospectId) {
      try {
        const res = await fetch(`${API}/api/behavior/${prospectId}`);
        if (res.ok) {
          const data = await res.json();
          this.behaviorForm = { ...data };
        } else {
          this.behaviorForm = { sales_motion: '', partner_model: '', decision_speed: '', culture: '', customer_segment: '', partnership_history: '', assessed_by: '' };
        }
      } catch (e) {
        this.behaviorForm = { sales_motion: '', partner_model: '', decision_speed: '', culture: '', customer_segment: '', partnership_history: '', assessed_by: '' };
      }
    },

    async saveBehavior() {
      if (!this.detailEntry) return;
      await fetch(`${API}/api/behavior/${this.detailEntry.prospect_id}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.behaviorForm),
      });
      this.showToast('Behavior profile saved.');
    },

    // ---- Intent ----

    async loadIntentSignals() {
      if (!this.detailEntry) return;
      const res = await fetch(`${API}/api/intent/${this.detailEntry.prospect_id}`);
      this.detailIntentSignals = await res.json();
    },

    async addIntentSignal() {
      if (!this.detailEntry || !this.intentForm.signal_detail.trim()) return;
      await fetch(`${API}/api/intent/${this.detailEntry.prospect_id}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.intentForm),
      });
      this.intentForm.signal_detail = '';
      await this.loadIntentSignals();
      await this.loadPipeline();
      this.showToast('Intent signal added.');
    },

    async deleteIntentSignal(signalId) {
      await fetch(`${API}/api/intent/${signalId}`, { method: 'DELETE' });
      await this.loadIntentSignals();
      await this.loadPipeline();
    },

    // ---- Identity Filters ----

    async loadFilters() {
      if (!this.selectedClientId) return;
      try {
        const res = await fetch(`${API}/api/filters/${this.selectedClientId}`);
        if (res.ok) {
          const data = await res.json();
          this.filterConfig.allowed_business_models = data.allowed_business_models ? JSON.parse(data.allowed_business_models) : [];
          this.filterConfig.allowed_stages = data.allowed_stages ? JSON.parse(data.allowed_stages) : [];
          this.filterConfig.min_employees = data.min_employees;
          this.filterConfig.max_employees = data.max_employees;
          this.filterConfig.excluded_verticals_text = data.excluded_verticals ? JSON.parse(data.excluded_verticals).join(', ') : '';
          this.filterConfig.notes = data.notes || '';
          this.hasFilters = true;
        } else {
          this.filterConfig = { allowed_business_models: [], allowed_stages: [], min_employees: null, max_employees: null, excluded_verticals_text: '', notes: '' };
          this.hasFilters = false;
        }
      } catch (e) {
        this.hasFilters = false;
      }
    },

    async saveFilters() {
      if (!this.selectedClientId) return;
      const excl = this.filterConfig.excluded_verticals_text ? this.filterConfig.excluded_verticals_text.split(',').map(s => s.trim()).filter(Boolean) : [];
      await fetch(`${API}/api/filters/${this.selectedClientId}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          allowed_business_models: JSON.stringify(this.filterConfig.allowed_business_models),
          allowed_stages: JSON.stringify(this.filterConfig.allowed_stages),
          min_employees: this.filterConfig.min_employees || null,
          max_employees: this.filterConfig.max_employees || null,
          excluded_verticals: JSON.stringify(excl),
          notes: this.filterConfig.notes,
        }),
      });
      this.hasFilters = true;
      this.showToast('Identity filters saved.');
    },

    async saveFiltersAndRescore() {
      await this.saveFilters();
      await this.scoreAll();
    },

    async previewFilters() {
      if (!this.selectedClientId) return;
      this.filterPreviewLoading = true;
      try {
        const excl = this.filterConfig.excluded_verticals_text ? this.filterConfig.excluded_verticals_text.split(',').map(s => s.trim()).filter(Boolean) : [];
        const body = {
          allowed_business_models: this.filterConfig.allowed_business_models || [],
          allowed_stages: this.filterConfig.allowed_stages || [],
          min_employees: this.filterConfig.min_employees || null,
          max_employees: this.filterConfig.max_employees || null,
          excluded_verticals: excl,
        };
        const res = await fetch(`${API}/api/filters/${this.selectedClientId}/preview`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (res.ok) this.filterPreview = await res.json();
      } finally {
        this.filterPreviewLoading = false;
      }
    },

    // Debounced auto-preview when any filter field changes
    scheduleFilterPreview() {
      clearTimeout(this._filterPreviewTimer);
      this._filterPreviewTimer = setTimeout(() => this.previewFilters(), 400);
    },

    async clearFilters() {
      if (!this.selectedClientId) return;
      if (!confirm('Clear all identity filters for this lens? Companies currently blocked will flow back into scoring.')) return;
      // Save an empty filter
      this.filterConfig = { allowed_business_models: [], allowed_stages: [], min_employees: null, max_employees: null, excluded_verticals_text: '', notes: '' };
      this.filterPreview = null;
      await this.saveFilters();
      await this.scoreAll();
      this.hasFilters = false;
      this.showToast('Filters cleared. Pipeline rescored.');
    },

    // ---- Client Refresh Menu ----

    async _isClientDataStale() {
      // Returns true if the client's business profile was refreshed >15 min ago.
      // If no profile exists or we can't tell, returns true (show the menu to offer refresh).
      if (!this.activeClient?.name) return true;
      try {
        const prospects = await (await fetch(`${API}/api/prospects?search=${encodeURIComponent(this.activeClient.name)}`)).json();
        const matching = prospects.find(p => p.name.toLowerCase() === this.activeClient.name.toLowerCase());
        if (!matching) return true;
        const profile = await (await fetch(`${API}/api/profiles/${matching.id}`)).json();
        if (!profile.last_refreshed) return true;
        // Server stores UTC without timezone suffix; append 'Z' so JS parses it as UTC
        const ts = profile.last_refreshed.endsWith('Z') ? profile.last_refreshed : profile.last_refreshed + 'Z';
        const minutes = (Date.now() - new Date(ts).getTime()) / (1000 * 60);
        return minutes > 15;
      } catch (e) {
        return true;
      }
    },

    async _computeLastRefreshInfo() {
      if (!this.selectedClientId) {
        this.lastRefreshInfo = 'unknown';
        return;
      }
      // Try to get the last_refreshed from the client's business profile
      try {
        // Find the prospect record matching this client name
        const prospects = await (await fetch(`${API}/api/prospects?search=${encodeURIComponent(this.activeClient?.name || '')}`)).json();
        const matching = prospects.find(p => p.name.toLowerCase() === (this.activeClient?.name || '').toLowerCase());
        if (matching) {
          const profile = await (await fetch(`${API}/api/profiles/${matching.id}`)).json();
          if (profile.last_refreshed) {
            const ts = profile.last_refreshed.endsWith('Z') ? profile.last_refreshed : profile.last_refreshed + 'Z';
            const d = new Date(ts);
            const minutes = Math.floor((Date.now() - d.getTime()) / (1000 * 60));
            if (minutes < 60) {
              this.lastRefreshInfo = minutes <= 0 ? 'just now' : `${minutes} min ago (${profile.generation_depth})`;
            } else {
              const days = Math.floor(minutes / (60 * 24));
              this.lastRefreshInfo = days === 0 ? `${Math.floor(minutes/60)} hour(s) ago (${profile.generation_depth})` : `${days} day(s) ago (${profile.generation_depth})`;
            }
          } else {
            this.lastRefreshInfo = 'never';
          }
        } else {
          this.lastRefreshInfo = 'unknown';
        }
      } catch (e) {
        this.lastRefreshInfo = 'unknown';
      }
    },

    async refreshOption(option) {
      if (this.refreshing) return;
      this.refreshing = true;
      this.refreshStatus = option;

      try {
        if (option === 'profile' || option === 'all') {
          // Re-enrich the client's own profile (find prospect, run Layer 1+2)
          const prospects = await (await fetch(`${API}/api/prospects?search=${encodeURIComponent(this.activeClient?.name || '')}`)).json();
          const matching = prospects.find(p => p.name.toLowerCase() === (this.activeClient?.name || '').toLowerCase());
          if (matching) {
            await fetch(`${API}/api/profiles/${matching.id}/generate?depth=enriched`, { method: 'POST' });
          }
        }

        if (option === 'pipeline' || option === 'all') {
          // Enrich all prospects in this client's pipeline
          await fetch(`${API}/api/profiles/bulk/enrich?client_id=${this.selectedClientId}`, { method: 'POST' });
        }

        if (option === 'rescore' || option === 'all') {
          await fetch(`${API}/api/pipeline/${this.selectedClientId}/score-all`, { method: 'POST' });
        }

        // Deep research is ONLY triggered by the explicit 'deep' option, never by 'all'
        if (option === 'deep') {
          // Queue deep research (cost-gated, needs explicit approval)
          const prospects = await (await fetch(`${API}/api/prospects?search=${encodeURIComponent(this.activeClient?.name || '')}`)).json();
          const matching = prospects.find(p => p.name.toLowerCase() === (this.activeClient?.name || '').toLowerCase());
          if (matching) {
            await fetch(`${API}/api/profiles/${matching.id}/generate?depth=deep`, { method: 'POST' });
            await this.loadNotifications();
          }
        }

        // Reload data
        await this.onClientChange();
        await this.loadActivity();

        // Close menu and show toast
        this.showRefreshMenu = false;
        const messages = {
          profile: 'Business profile refreshed (free).',
          pipeline: 'All pipeline profiles re-enriched (free).',
          rescore: 'Pipeline rescored (free).',
          deep: 'Deep research queued. Check the alert bar to approve (~$0.05).',
          all: 'All free refreshes complete. No charges. No prompts.',
        };
        this.showToast(messages[option] || 'Refresh complete.');
      } catch (e) {
        console.error('Refresh error:', e);
        this.showToast('Refresh failed. Check console for details.');
      } finally {
        this.refreshing = false;
        this.refreshStatus = '';
      }
    },

    // ---- Criterion Score Override ----

    async overrideScore(criterionScore, newScore) {
      if (!this.detailEntry) return;
      if (criterionScore.score === newScore) return;

      const oldScore = criterionScore.score;
      criterionScore.score = newScore;  // Optimistic update

      const params = new URLSearchParams({
        score: newScore,
        reasoning: `Manual override from ${oldScore} to ${newScore}`,
      });

      try {
        const res = await fetch(`${API}/api/pipeline/${this.detailEntry.id}/scores/${criterionScore.criterion_id}?${params}`, {
          method: 'PUT',
        });
        if (res.ok) {
          const data = await res.json();
          // Update the detail entry with new scores
          this.detailEntry.pmf_score = data.pmf_score;
          this.detailEntry.matchmaker_score = data.matchmaker_score;
          this.detailEntry.tier = data.tier;

          // Update reasoning locally
          criterionScore.reasoning = `Manual override from ${oldScore} to ${newScore}`;

          if (data.tier_changed) {
            this.showToast(`Score updated. ${criterionScore.criterion_name} changed tier to ${data.tier.toUpperCase()}.`);
          } else {
            this.showToast(`Score updated. Matchmaker: ${data.matchmaker_score}`);
          }

          // Refresh the breakdown card so the inline card matches the new score
          try {
            const bRes = await fetch(`${API}/api/pipeline/${this.detailEntry.id}/breakdown`);
            if (bRes.ok) this.detailBreakdown = await bRes.json();
          } catch (e) {}
          this._invalidateBreakdownCache();
          // Reload pipeline to reflect changes in the table
          await this.loadPipeline();
        } else {
          criterionScore.score = oldScore;  // Revert
          this.showToast('Score update failed.');
        }
      } catch (e) {
        criterionScore.score = oldScore;
        console.error(e);
      }
    },

    // ---- Deep Research Offer (post-creation) ----

    async approveDeepResearch() {
      // Queue the Deep Research action for approval
      if (!this.selectedClientId) return;
      try {
        const prospects = await (await fetch(`${API}/api/prospects?search=${encodeURIComponent(this.deepResearchOfferName)}`)).json();
        const matching = prospects.find(p => p.name.toLowerCase() === this.deepResearchOfferName.toLowerCase());
        if (matching) {
          await fetch(`${API}/api/profiles/${matching.id}/generate?depth=deep`, { method: 'POST' });
          await this.loadNotifications();
          this.showToast(`Deep research queued for ${this.deepResearchOfferName}. Check the alert bar to approve (~$0.05).`);
        }
      } catch (e) {
        console.error(e);
      }
      this.showDeepResearchOffer = false;
      this.deepResearchOfferName = '';
    },

    skipDeepResearch() {
      this.showDeepResearchOffer = false;
      this.deepResearchOfferName = '';
      this.showToast(`${this.deepResearchOfferName || 'Client'} added (free). You can add Deep Research anytime via the Refresh button.`);
    },

    // ---- Business Profile ----

    async loadBusinessProfile() {
      if (!this.detailEntry) return;
      try {
        const res = await fetch(`${API}/api/profiles/${this.detailEntry.prospect_id}`);
        if (res.ok) {
          this.businessProfile = await res.json();
        }
        // Also load the prospect to get the current type
        const pRes = await fetch(`${API}/api/prospects/${this.detailEntry.prospect_id}`);
        if (pRes.ok) {
          const prospect = await pRes.json();
          this.currentProspectType = prospect.type || '';
        }
      } catch (e) {
        this.businessProfile = null;
        this.currentProspectType = '';
      }
    },

    async updateProspectType() {
      if (!this.detailEntry || !this.currentProspectType) return;
      this.updatingType = true;
      try {
        const res = await fetch(`${API}/api/prospects/${this.detailEntry.prospect_id}/type?new_type=${encodeURIComponent(this.currentProspectType)}`, {
          method: 'PUT',
        });
        if (res.ok) {
          const data = await res.json();
          this.showToast(`Type updated to "${data.new_type}". Behavior profile + ${data.pipelines_rescored} pipeline(s) rescored.`);
          // Reload pipeline to see new scores
          await this.loadPipeline();
          // Reload behavior tab data
          await this.loadBehavior(this.detailEntry.prospect_id);
        } else {
          this.showToast('Type update failed.');
        }
      } catch (e) {
        console.error(e);
        this.showToast('Error updating type.');
      } finally { this.updatingType = false; }
    },

    async deepResearchProfile() {
      if (!this.detailEntry) return;
      this.deepResearching = true;
      try {
        const res = await fetch(`${API}/api/profiles/${this.detailEntry.prospect_id}/generate?depth=deep`, { method: 'POST' });
        const data = await res.json();
        if (data.status === 'pending_approval') {
          this.showToast(data.message);
          await this.loadNotifications();
          this.showNotificationsPanel = true;
        } else {
          this.businessProfile = data;
          this.showToast('Deep profile generated.');
        }
      } finally { this.deepResearching = false; }
    },

    async enrichAll() {
      if (!this.selectedClientId) return;
      if (!confirm('Enrich profiles for all companies? This is free and uses local heuristics plus Apollo/HubSpot if configured. Pipeline will rescore automatically at the end.')) return;
      this.enriching = true;
      try {
        const res = await fetch(`${API}/api/profiles/bulk/enrich?client_id=${this.selectedClientId}`, { method: 'POST' });
        const data = await res.json();
        // Auto-rescore so enriched profile data actually moves Matchmaker scores in the pipeline
        await fetch(`${API}/api/pipeline/${this.selectedClientId}/score-all`, { method: 'POST' });
        this._invalidateBreakdownCache();
        await this.loadPipeline();
        await this.loadNotifications();
        this.showToast(`${data.message} Pipeline rescored.`);
      } finally { this.enriching = false; }
    },

    async bulkInferBehavior() {
      if (!confirm('Auto-populate behavior profiles for all prospects using type-based heuristics? This is free and unlocks the Friction scoring layer.')) return;
      this.inferringBehavior = true;
      try {
        const res = await fetch(`${API}/api/behavior/bulk/infer`, { method: 'POST' });
        const data = await res.json();

        // Rescore active client so Friction column populates
        if (this.selectedClientId) {
          await fetch(`${API}/api/pipeline/${this.selectedClientId}/score-all`, { method: 'POST' });
          await this.loadPipeline();
        }

        this.showToast(`Behavior inferred: ${data.created} created, ${data.skipped_existing} already had profiles, ${data.skipped_no_type} skipped (no type). Friction column now populated.`, 8000);
      } finally { this.inferringBehavior = false; }
    },

    // ---- Helpers ----

    setDensity(d) {
      this.tableDensity = d;
      try { localStorage.setItem('bd_table_density', d); } catch (e) {}
    },

    toggleColumn(key) {
      this.columnVisibility[key] = !this.columnVisibility[key];
      try { localStorage.setItem('bd_column_visibility', JSON.stringify(this.columnVisibility)); } catch (e) {}
    },

    _handleGlobalKey(e) {
      // Ignore when typing in an input, textarea, or contenteditable
      const tag = (e.target.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.target.isContentEditable) {
        // Escape still works inside inputs to blur
        if (e.key === 'Escape') e.target.blur();
        return;
      }

      // / → focus pipeline search
      if (e.key === '/') {
        const el = document.querySelector('input[placeholder^="Search pipeline"]');
        if (el) { e.preventDefault(); el.focus(); el.select(); }
        return;
      }

      // Esc → close slide panel / menus
      if (e.key === 'Escape') {
        if (this.detailOpen) { this.detailOpen = false; return; }
        if (this.showColumnMenu) { this.showColumnMenu = false; return; }
        if (this.clientDropdownOpen) { this.clientDropdownOpen = false; return; }
      }

      // j / k / Enter on pipeline view
      if (this.view !== 'pipeline') return;
      const entries = this.filteredPipelineEntries();
      if (entries.length === 0) return;
      const currentIdx = this.detailEntry
        ? entries.findIndex(x => x.id === this.detailEntry.id)
        : -1;

      if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault();
        const next = Math.min(entries.length - 1, currentIdx + 1);
        this.openDetail(entries[next]);
      } else if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault();
        const prev = Math.max(0, currentIdx - 1);
        this.openDetail(entries[prev]);
      } else if (e.key === 'Enter' && currentIdx === -1 && entries.length) {
        e.preventDefault();
        this.openDetail(entries[0]);
      }
    },

    filteredPipelineEntries() {
      const q = (this.pipelineSearch || '').trim().toLowerCase();
      if (!q) return this.pipelineEntries;
      return this.pipelineEntries.filter(e => {
        const name = (e.prospect_name || '').toLowerCase();
        const type = (e.prospect_type || '').toLowerCase();
        const contact = (e.best_contact || '').toLowerCase();
        return name.includes(q) || type.includes(q) || contact.includes(q);
      });
    },

    rsDots(score) {
      let html = '';
      for (let i = 1; i <= 5; i++) { html += i <= score ? '<span class="dot-filled">&#9679;</span>' : '<span class="dot-empty">&#9679;</span>'; }
      return html;
    },

    formatDate(dateStr) {
      if (!dateStr) return '';
      return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
    },
  };
}

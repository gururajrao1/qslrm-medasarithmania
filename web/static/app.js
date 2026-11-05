(() => {
  const body = document.getElementById("queueBody");
  const modelChip = document.getElementById("modelChip");
  const countChip = document.getElementById("countChip");
  const statusLine = document.getElementById("statusLine");
  const risingBadge = document.getElementById("risingBadge");
  const queueNote = document.getElementById("queueNote");
  const sourceGrid = document.getElementById("sourceGrid");
  const drawer = document.getElementById("drawer");
  const backdrop = document.getElementById("drawerBackdrop");
  const drawerTitle = document.getElementById("drawerTitle");
  const drawerSub = document.getElementById("drawerSub");
  const searchBox = document.getElementById("searchBox");
  const filterSponsor = document.getElementById("filterSponsor");
  const filterMolecule = document.getElementById("filterMolecule");
  const filterRegion = document.getElementById("filterRegion");
  const filterDrugClass = document.getElementById("filterDrugClass");
  const risingOnly = document.getElementById("risingOnly");
  const prevPage = document.getElementById("prevPage");
  const nextPage = document.getElementById("nextPage");
  const pageInfo = document.getElementById("pageInfo");
  const sortBy = document.getElementById("sortBy");
  const themeToggle = document.getElementById("themeToggle");
  const filterAction = document.getElementById("filterAction");
  const minFused = document.getElementById("minFused");
  const minN = document.getElementById("minN");
  const pageSizeSel = document.getElementById("pageSize");
  const firstPage = document.getElementById("firstPage");
  const lastPage = document.getElementById("lastPage");
  const cancelJobBtn = document.getElementById("cancelJobBtn");
  const jobProgress = document.getElementById("jobProgress");

  const liveChip = document.getElementById("liveChip");
  const pullAllBtn = document.getElementById("pullAllBtn");
  let items = [];
  let deep = null;
  let streamSocket = null;
  let streamEvents = 0;
  let page = 0;
  let pageSize = 100;
  let pullPoll = null;
  let selectedKey = null;
  let activeJob = null;
  let lastTotal = 0;
  let narrShown = 5;
  let litShown = 8;

  const fmt = (v, d = 2) => (v == null || Number.isNaN(v) ? "—" : Number(v).toFixed(d));
  const pct = (v) => (v == null ? "0%" : `${Math.round(Number(v) * 100)}%`);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[c]);

  const savedTheme = localStorage.getItem("qslrm-theme") || "dark";
  document.documentElement.setAttribute("data-theme", savedTheme);
  themeToggle.addEventListener("click", () => {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("qslrm-theme", next);
  });

  function openDrawer() {
    drawer.classList.add("open");
    drawer.setAttribute("aria-hidden", "false");
    backdrop.hidden = false;
  }
  function closeDrawer() {
    drawer.classList.remove("open");
    drawer.setAttribute("aria-hidden", "true");
    backdrop.hidden = true;
  }
  document.getElementById("drawerClose").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });
  document.getElementById("drawer").addEventListener("click", (e) => {
    const t = e.target;
    if (!t || !t.id) return;
    if (t.id === "moreNarr") { narrShown = 10000; if (deep) renderTabs(deep); }
    if (t.id === "moreLit") { litShown = 10000; if (deep) renderTabs(deep); }
    if (t.id === "draftClause") { draftClause(); }
  });
  backdrop.addEventListener("click", closeDrawer);

  document.getElementById("tabs").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-tab]");
    if (!btn) return;
    document.querySelectorAll("#tabs button").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
  });

  function setAttrs(item) {
    document.getElementById("fusedValue").textContent = fmt(item.fused_score, 1);
    const band = item.fused_band;
    if (band) {
      document.getElementById("fusedValue").textContent += ` (${fmt(band.lo, 1)}-${fmt(band.hi, 1)})`;
      document.getElementById("fusedValue").title = "Uncertainty band from weight perturbation; weights fitted vs boxed-warning labels";
    } else {
      document.getElementById("fusedValue").title = "Band unavailable — run Phase 3 calibration";
    }
    [
      ["attrDosePct", "attrDoseFill", item.attr_dose],
      ["attrOffPct", "attrOffFill", item.attr_offtarget],
      ["attrTrPct", "attrTrFill", item.attr_transcriptomic],
      ["attrGenPct", "attrGenFill", item.attr_genetic],
    ].forEach(([pid, fid, v]) => {
      document.getElementById(pid).textContent = pct(v);
      document.getElementById(fid).style.width = pct(v);
    });
    const flags = [];
    if (item.rising_signal) flags.push(`<span class="pill rising">Rising</span>`);
    if (item.action_flag) flags.push(`<span class="pill action">${esc(item.action_flag)}</span>`);
    if (item.is_bbw_or_rems) flags.push(`<span class="pill action">BBW</span>`);
    document.getElementById("flagStack").innerHTML = flags.join("") || `<span class="pill">monitor</span>`;
  }

  function kmSvg(points) {
    if (!points || !points.length) return `<p class="panel-note">No onset curve.</p>`;
    const w = 620, h = 140, pad = 16;
    const xs = points.map((p) => p.week);
    const xmin = Math.min(...xs), xmax = Math.max(...xs) || 1;
    const sx = (x) => pad + ((x - xmin) / (xmax - xmin || 1)) * (w - 2 * pad);
    const sy = (y) => h - pad - (y * (h - 2 * pad));
    let d = "";
    points.forEach((p, i) => {
      d += `${i ? "L" : "M"}${sx(p.week).toFixed(1)},${sy(p.survival_prob).toFixed(1)} `;
    });
    const stroke = getComputedStyle(document.documentElement).getPropertyValue("--teal").trim() || "#2dd4bf";
    return `<div class="km"><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
      <path d="${d}" fill="none" stroke="${stroke}" stroke-width="2.5"/>
    </svg></div>`;
  }

  function sparkline(hist) {
    if (!hist || hist.length < 2) return `<p class="panel-note">Not enough periods for a trend.</p>`;
    const w = 620, h2 = 90, pad = 14;
    const ys = hist.map((p) => Number(p.ror) || 0);
    const ymin = Math.min(...ys), ymax = Math.max(...ys);
    const sx = (i) => pad + (i / Math.max(1, hist.length - 1)) * (w - 2 * pad);
    const sy = (y) => h2 - pad - ((y - ymin) / ((ymax - ymin) || 1)) * (h2 - 2 * pad);
    const dAttr = ys.map((y, i) => `${i ? "L" : "M"}${sx(i).toFixed(1)},${sy(y).toFixed(1)}`).join(" ");
    const labels = hist.map((p) => esc(p.period)).join(" | ");
    return `<div class="km"><svg viewBox="0 0 ${w} ${h2}" preserveAspectRatio="none"><path d="${dAttr}" fill="none" stroke-width="2.5" stroke="currentColor"/></svg><p class="panel-note">${labels}</p></div>`;
  }

  function renderTabs(d) {
    document.getElementById("tab-decisions").innerHTML = (d.decisions || []).map((c) => `
      <div class="card kind-${esc(c.kind)}"><h3>${esc(c.title)}</h3><p>${esc(c.body)}</p></div>`
    ).join("") || `<p class="panel-note">No decision cards — pair is below action thresholds. Keep monitoring.</p>`;
    document.getElementById("tab-decisions").insertAdjacentHTML("beforeend", `
      <div class="pair-actions">
        <a class="btn ghost" target="_blank" href="/v1/dsur?format=html&drug_id=${encodeURIComponent(d.drug_id || "")}">Pair DSUR</a>
        <a class="btn ghost" target="_blank" href="/v1/deep-dive/${encodeURIComponent(d.drug_id || "")}/${encodeURIComponent(d.ae_term_id || "")}">Pair JSON</a>
      </div>`);

    document.getElementById("tab-proteomics").innerHTML = `
      <p class="section-label">ChEMBL · S<sub>off</sub> ${fmt(d.s_off, 3)}</p>
      <table class="mini-table"><thead><tr><th>Gene</th><th>nM</th><th>Off?</th><th>PDB</th></tr></thead>
      <tbody>${(d.proteomics || []).map((t) =>
        `<tr><td>${esc(t.gene_symbol)}</td><td class="mono">${fmt(t.affinity_nm, 1)}</td>
         <td>${t.is_off_target ? "yes" : "on"}</td><td class="mono">${esc(t.pdb_id || "—")}</td></tr>`
      ).join("") || `<tr><td colspan="4">None</td></tr>`}</tbody></table>`;

    const tr = [...(d.transcriptomics || [])].sort((a, b) => Math.abs(b.z_score) - Math.abs(a.z_score));
    document.getElementById("tab-transcriptomics").innerHTML = `
      <p class="section-label">LINCS · S<sub>trans</sub> ${fmt(d.s_trans, 3)}</p>
      <table class="mini-table"><thead><tr><th>Gene</th><th>z</th><th>dir</th></tr></thead>
      <tbody>${tr.slice(0, 15).map((t) =>
        `<tr><td>${esc(t.gene_symbol)}</td><td class="mono">${fmt(t.z_score)}</td><td>${esc(t.direction || "—")}</td></tr>`
      ).join("") || `<tr><td colspan="3">None</td></tr>`}</tbody></table>`;

    document.getElementById("tab-genomics").innerHTML = `
      <p class="section-label">ClinVar / PharmGKB · S<sub>gen</sub> ${fmt(d.s_gen, 3)}</p>
      <table class="mini-table"><thead><tr><th>Gene</th><th>Impact</th><th>Effect</th></tr></thead>
      <tbody>${(d.genomics || []).map((g) =>
        `<tr><td>${esc(g.gene_symbol)}</td><td>${esc(g.metabolizer_impact || g.rsid || "—")}</td>
         <td class="mono">${fmt(g.effect_size)}</td></tr>`
      ).join("") || `<tr><td colspan="3">None</td></tr>`}</tbody></table>`;

    document.getElementById("tab-trials").innerHTML = `
      ${kmSvg(d.onset_curve)}
      <table class="mini-table"><thead><tr><th>NCT</th><th>Phase</th><th>Arm</th><th>Events</th></tr></thead>
      <tbody>${(d.trials || []).slice(0, 12).map((t) =>
        `<tr><td>${esc(t.nct_id)}</td><td>${esc(t.phase || "—")}</td><td>${esc(t.arm)}</td>
         <td class="mono">${t.event_count ?? "—"}/${t.subjects_at_risk ?? "—"}</td></tr>`
      ).join("") || `<tr><td colspan="4">None</td></tr>`}</tbody></table>`;

    const peers = d.class_comparison || [];
    document.getElementById("tab-class").innerHTML = peers.map((p) => {
      const dd = Math.round((p.attr_dose || 0) * 100);
      const o = Math.round((p.attr_offtarget || 0) * 100);
      const t = Math.round((p.attr_transcriptomic || 0) * 100);
      const g = Math.round((p.attr_genetic || 0) * 100);
      return `<div class="compare-row ${p.is_selected ? "selected" : ""}">
        <div class="name">${esc(p.drug_name)} · ${fmt(p.fused_score, 1)}</div>
        <div class="compare-bars">
          <span class="d" style="width:${dd}%"></span>
          <span class="o" style="width:${o}%"></span>
          <span class="t" style="width:${t}%"></span>
          <span class="g" style="width:${g}%"></span>
        </div>
      </div>`;
    }).join("") || `<p class="panel-note">No peers.</p>`;

    const v = d.velocity;
    document.getElementById("tab-pv").innerHTML = `
      <div class="kv">
        <div><span class="k">PRR</span><span class="v">${fmt(d.prr)}</span></div>
        <div><span class="k">ROR (95% CI)</span><span class="v">${fmt(d.ror)} [${fmt(d.ror_ci_low)}, ${fmt(d.ror_ci_high)}]</span></div>
        <div><span class="k">ΔROR</span><span class="v">${v ? fmt(v.delta_ror) : "—"}</span></div>
        <div><span class="k">Serious</span><span class="v">${pct(d.serious_rate)}</span></div>
        <div><span class="k">n reports</span><span class="v">${d.n_reports ?? "none"}</span></div>
        <div><span class="k">PRR chi2</span><span class="v">${fmt(d.prr_chi2, 1)}</span></div>
        <div><span class="k">IC025</span><span class="v">${fmt(d.ic025)}</span></div>
        <div><span class="k">EB05</span><span class="v">${fmt(d.eb05)}</span></div>
      </div>
      <p class="section-label">ROR trend with 95% CI per period</p>
      ${sparkline(d.velocity_history)}
      <table class="mini-table"><thead><tr><th>Period</th><th>ROR</th><th>CI</th><th>n</th></tr></thead>
      <tbody>${(d.velocity_history || []).map((h) =>
        `<tr><td>${esc(h.period)}</td><td class="mono">${fmt(h.ror)}</td>
         <td class="mono">[${fmt(h.ror_ci_low)}, ${fmt(h.ror_ci_high)}]</td><td class="mono">${h.n11 ?? "none"}</td></tr>`
      ).join("") || `<tr><td colspan="4">No period history</td></tr>`}</tbody></table>
      <div class="kv" style="display:none">
      </div>
      <table class="mini-table"><thead><tr><th>Stratum</th><th>Value</th><th>Lift</th></tr></thead>
      <tbody>${(d.demographics || []).map((x) =>
        `<tr><td>${esc(x.stratum_type)}</td><td>${esc(x.stratum_value)}</td>
         <td class="mono">${x.mh_ror != null ? "MH " + fmt(x.mh_ror) : x.lift_vs_background == null ? "—" : fmt(x.lift_vs_background)}</td></tr>`
      ).join("") || `<tr><td colspan="3">None</td></tr>`}</tbody></table>`;

    const lit = d.literature || [];
    const sider = d.sider_labels || [];
    const ev = (d.evidence_sources || []).join(", ") || "none";
    document.getElementById("tab-literature").innerHTML = `
      <p class="section-label">Evidence sources for pair · ${esc(ev)}</p>
      <p class="section-label">Label / LRT frequency (SIDER · OnSIDES · Open Targets)</p>
      <table class="mini-table"><thead><tr><th>Source</th><th>PT</th><th>Frequency</th><th>Match</th></tr></thead>
      <tbody>${sider.map((s) =>
        `<tr class="${s.matches_pair ? "row-match" : ""}"><td>${esc(s.source)}</td><td>${esc(s.pt_string)}</td>
         <td>${esc(s.frequency || "—")}</td><td>${s.matches_pair ? "pair" : "—"}</td></tr>`
      ).join("") || `<tr><td colspan="4">No label rows</td></tr>`}</tbody></table>
      <p class="section-label" style="margin-top:1rem">PubMed / Europe PMC / BioDEX / Kidsides</p>
      ${lit.slice(0, litShown).map((p) => `
        <div class="lit-card ${p.matches_pair ? "match" : ""}">
          <div class="lit-meta">${esc(p.source)}${p.extractor ? ` · ${esc(p.extractor)}` : ""} · ${esc(p.pmid)}${p.year ? ` · ${p.year}` : ""}${p.citation_count != null ? ` · ${p.citation_count} cites` : ""}</div>
          <div class="lit-title">${esc(p.title)}</div>
          <p class="panel-note">${esc(p.snippet || "")}</p>
        </div>`
      ).join("") || `<p class="panel-note">No literature evidence.</p>`}
      ${lit.length > litShown ? `<button type="button" class="btn ghost" id="moreLit">Show all (${lit.length})</button>` : ""}`;

    document.getElementById("tab-protocol").innerHTML = (d.protocol_exclusions || []).map((p) => `
      <div class="clause">${esc(p.clause_text)}</div>
      <p class="panel-note">${esc(p.rationale)}</p>`
    ).join("") || `<p class="panel-note">No exclusion clause yet — generate a draft from the top variant below.</p>`;
    document.getElementById("tab-protocol").insertAdjacentHTML("beforeend", `
      <button type="button" class="btn primary" id="draftClause">Generate draft clause</button>
      <p class="panel-note">Drafts persist for review; validate before protocol use.</p>`);
    document.getElementById("tab-ddi").innerHTML = `
      <table class="mini-table"><thead><tr><th>Concomitant</th><th>Enzyme</th><th>Risk</th><th>Mechanism</th></tr></thead>
      <tbody>${(d.ddi || []).map((x) =>
        `<tr><td>${esc(x.concomitant)}</td><td>${esc(x.enzyme || "—")}</td>
         <td>${esc(x.risk_level || "—")}</td><td>${esc(x.mechanism || x.notes || "—")}</td></tr>`
      ).join("") || `<tr><td colspan="4">No DDI rows</td></tr>`}</tbody></table>`;
    document.getElementById("tab-narratives").innerHTML = `
      ${(d.narratives || []).slice(0, narrShown).map((x) =>
        `<div class="lit-card"><div class="lit-meta">${esc(x.case_id)}${x.country ? ` · ${esc(x.country)}` : ""}</div>
         <p class="panel-note">${esc(x.narrative || "")}</p></div>`
      ).join("") || `<p class="panel-note">No narratives.</p>`}
      ${(d.narratives || []).length > narrShown ? `<button type="button" class="btn ghost" id="moreNarr">Show all (${(d.narratives || []).length})</button>` : ""}
      <p class="section-label">Extracted entities (${(d.narrative_entities || []).length})</p>
      <table class="mini-table"><thead><tr><th>Case</th><th>Type</th><th>Text</th><th>Conf</th></tr></thead>
      <tbody>${(d.narrative_entities || []).slice(0, 12).map((x) =>
        `<tr><td>${esc(x.case_id)}</td><td>${esc(x.entity_type)}</td>
         <td>${esc(x.entity_text)}</td><td class="mono">${fmt(x.confidence)}</td></tr>`
      ).join("") || `<tr><td colspan="4">None</td></tr>`}</tbody></table>`;
  }

  async function draftClause() {
    if (!deep || !deep.drug_id || !deep.ae_term_id) return;
    try {
      const r = await fetch(`/v1/protocol/draft?drug_id=${encodeURIComponent(deep.drug_id)}&ae_term_id=${encodeURIComponent(deep.ae_term_id)}`, { method: "POST" });
      if (!r.ok) throw new Error(`draft ${r.status}`);
      await r.json();
      const dr = await fetch(`/v1/deep-dive/${encodeURIComponent(deep.drug_id)}/${encodeURIComponent(deep.ae_term_id)}`);
      if (!dr.ok) throw new Error(`deep-dive ${dr.status}`);
      deep = await dr.json();
      setAttrs(deep);
      renderTabs(deep);
      statusLine.textContent = "Draft clause saved to protocol tab";
    } catch (err) {
      statusLine.textContent = `Draft failed: ${err.message}`;
    }
  }

  async function selectRow(item, tr) {
    selectedKey = `${item.drug_id}||${item.ae_term_id}`;
    narrShown = 5;
    litShown = 8;
    document.querySelectorAll("#queueBody tr").forEach((el) => el.classList.remove("active"));
    if (tr) tr.classList.add("active");
    drawerTitle.textContent = `${item.drug_name} ↔ ${item.pt_string}`;
    drawerSub.textContent = [item.sponsor_company, item.brand_name].filter(Boolean).join(" · ");
    setAttrs(item);
    openDrawer();
    try {
      const dr = await fetch(`/v1/deep-dive/${encodeURIComponent(item.drug_id)}/${encodeURIComponent(item.ae_term_id)}`);
      if (!dr.ok) throw new Error(`deep-dive ${dr.status}`);
      deep = await dr.json();
      setAttrs(deep);
      renderTabs(deep);
    } catch (err) {
      document.getElementById("tab-decisions").innerHTML = `<p class="panel-note">${esc(err)}</p>`;
    }
  }

  async function loadQueue(preferredTotal) {
    // Paged ranked set; chip uses API `total` (not page length)
    const params = new URLSearchParams({ limit: String(pageSize), offset: String(page * pageSize), sort: sortBy.value || "fused" });
    if (searchBox.value.trim()) params.set("q", searchBox.value.trim());
    if (filterSponsor.value) params.set("sponsor", filterSponsor.value);
    if (filterMolecule.value) params.set("molecule_type", filterMolecule.value);
    if (filterRegion.value) params.set("region", filterRegion.value);
    if (filterDrugClass && filterDrugClass.value) params.set("drug_class", filterDrugClass.value);
    if (risingOnly && risingOnly.checked) params.set("rising_only", "true");
    if (filterAction && filterAction.value === "needed") params.set("action_needed", "true");
    if (filterAction && filterAction.value === "none") params.set("action_needed", "false");
    if (minFused && minFused.value !== "") params.set("min_fused", minFused.value);
    if (minN && minN.value !== "") params.set("min_n", minN.value);
    params.set("sort", sortBy.value);
    const resp = await fetch(`/v1/risk-scores?${params}`);
    if (!resp.ok) throw new Error(`queue ${resp.status}`);
    const data = await resp.json();
    if (pageInfo) pageInfo.textContent = `Page ${page + 1} · ${pageSize}/page`;
    if (prevPage) prevPage.disabled = page === 0;
    if (nextPage) nextPage.disabled = (page + 1) * pageSize >= (data.total ?? 0);
    lastTotal = data.total ?? 0;
    if (pageInfo) {
      const pages = Math.max(1, Math.ceil(lastTotal / pageSize));
      pageInfo.textContent = `Page ${page + 1} of ${pages}`;
    }
    if (firstPage) firstPage.disabled = page === 0;
    if (lastPage) lastPage.disabled = (page + 1) * pageSize >= lastTotal;
    const ex = new URLSearchParams(params);
    ex.delete("limit"); ex.delete("offset"); ex.delete("sort");
    const csvLink = document.getElementById("csvLink");
    if (csvLink) csvLink.href = `/v1/audit?format=csv&limit=500&${ex}`;
    const dsurLink = document.getElementById("dsurLink");
    if (dsurLink) dsurLink.href = "/v1/dsur?format=html";
    items = data.items || [];
    const total = Number(
      preferredTotal != null
        ? preferredTotal
        : (data.total != null ? data.total : items.length)
    );
    countChip.textContent = `${total} pairs`;
    queueNote.textContent = items.length < total
      ? `Showing ${items.length} of ${total} ranked pairs`
      : `${total} ranked pairs`;
    const rising = data.rising_count || items.filter((i) => i.rising_signal).length;
    if (rising > 0) {
      risingBadge.textContent = `Rising · ${rising}`;
      risingBadge.classList.remove("hidden");
    } else risingBadge.classList.add("hidden");

    if (!items.length) {
      body.innerHTML = `<tr><td colspan="12" class="empty">No matches.</td></tr>`;
      return;
    }
    body.innerHTML = "";
    items.forEach((item) => {
      const tr = document.createElement("tr");
      const flag = item.rising_signal
        ? `<span class="pill rising">Rising</span>`
        : (item.action_flag ? `<span class="pill action">${esc(item.action_flag)}</span>` : "—");
      tr.innerHTML = `
        <td class="mono">${item.rank}</td>
        <td>${esc(item.drug_name)}</td>
        <td>${esc(item.sponsor_company || "—")}</td>
        <td>${esc(item.pt_string)}</td>
        <td class="mono">${fmt(item.fused_score, 1)}</td>
        <td>${flag}</td>
        <td class="mono">${item.delta_ror == null ? "—" : fmt(item.delta_ror)}</td>
        <td class="mono">${pct(item.attr_dose)}</td>
        <td class="mono">${pct(item.attr_offtarget)}</td>
        <td class="mono">${pct(item.attr_transcriptomic)}</td>
        <td class="mono">${pct(item.attr_genetic)}</td>
        <td class="mono">${item.n_reports ?? "—"}</td>`;
      tr.tabIndex = 0;
      tr.addEventListener("click", () => { selectRow(item, tr); drawer.setAttribute("tabindex", "-1"); drawer.focus({ preventScroll: true }); });
      tr.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectRow(item, tr); } });
      body.appendChild(tr);
    });
    const hit = selectedKey && items.find((it) => `${it.drug_id}||${it.ae_term_id}` === selectedKey);
    if (hit) {
      const tr = body.children[items.indexOf(hit)];
      selectRow(hit, tr || undefined);
    } else {
      selectedKey = null;
      closeDrawer();
    }
  }

  function renderCatalog(cat) {
    const d = cat.domains || {};
    const cards = [
      { name: "FAERS", metric: d.pharmacovigilance?.pv_case ?? 0 },
      { name: "LINCS", metric: d.transcriptomics?.transcript_signature ?? 0 },
      { name: "Targets", metric: d.proteomics?.drug_target ?? 0 },
      { name: "Trials", metric: d.clinical_trials?.trial_ae ?? 0 },
      { name: "Literature", metric: d.literature?.pubmed_europepmc ?? 0 },
      { name: "Labels", metric: d.literature?.sider_labels ?? 0 },
      { name: "NDAs", metric: d.regulatory_orange_book?.drugs_with_nda ?? 0 },
      { name: "Ledger", metric: d.streaming?.event_ledger ?? 0 },
      { name: "Fused", metric: cat.queue?.fused_pairs ?? 0 },
    ];
    sourceGrid.innerHTML = cards.map((c) => `
      <div class="source-card compact-card">
        <div class="src-name">${esc(c.name)}</div>
        <div class="src-metric">${esc(c.metric)}</div>
      </div>`).join("");
    const options = cat.filters?.sponsor_options || (cat.filters?.sponsors || []).map((s) => ({ name: s, pair_count: null }));
    filterSponsor.innerHTML = `<option value="">All sponsors</option>` +
      options
        .filter((s) => (s.pair_count == null ? true : s.pair_count > 0))
        .map((s) => {
          const label = s.pair_count != null ? `${s.name} (${s.pair_count})` : s.name;
          return `<option value="${esc(s.name)}">${esc(label)}</option>`;
        })
        .join("");
    if (filterDrugClass) {
      const classes = cat.filters?.drug_classes || [];
      const kept = filterDrugClass.value;
      filterDrugClass.innerHTML = `<option value="">All classes</option>` +
        classes.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
      if (classes.includes(kept)) filterDrugClass.value = kept;
    }
  }

  // drug-class options are populated in renderCatalog above
  let debounce;
  const reload = () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => loadQueue().catch(console.error), 150);
  };
  const resetPage = () => { page = 0; };
  [searchBox, filterSponsor, filterMolecule, filterRegion, sortBy, filterDrugClass, risingOnly, filterAction, minFused, minN, pageSizeSel].forEach((el) => {
    if (!el) return;
    el.addEventListener("change", () => { resetPage(); reload(); });
    el.addEventListener("input", () => { resetPage(); reload(); });
  });
  if (prevPage) prevPage.addEventListener("click", () => { if (page > 0) { page -= 1; loadQueue().catch((e) => { statusLine.textContent = `Queue failed · ${e.message}`; }); } });
  if (nextPage) nextPage.addEventListener("click", () => { page += 1; loadQueue().catch((e) => { statusLine.textContent = `Queue failed · ${e.message}`; }); });
  const pageErr = (e) => { statusLine.textContent = `Queue failed: ${e.message}`; };
  if (firstPage) firstPage.addEventListener("click", () => { page = 0; loadQueue().catch(pageErr); });
  if (lastPage) lastPage.addEventListener("click", () => { page = Math.max(0, Math.ceil(lastTotal / pageSize) - 1); loadQueue().catch(pageErr); });
  if (pageSizeSel) pageSizeSel.addEventListener("change", () => { pageSize = Number(pageSizeSel.value) || 100; });
  [].forEach((el) => { // superseded by the resetPage wiring above
    el.addEventListener("change", () => {});
    el.addEventListener("input", () => {});
  });

  function setLive(state, detail) {
    if (!liveChip) return;
    liveChip.classList.remove("live-on", "live-off", "live-pulse");
    if (state === "on") {
      liveChip.classList.add("live-on");
      liveChip.textContent = `● Live${detail ? " · " + detail : ""}`;
    } else if (state === "pulse") {
      liveChip.classList.add("live-on", "live-pulse");
      liveChip.textContent = `● ${detail || "patch"}`;
    } else {
      liveChip.classList.add("live-off");
      liveChip.textContent = "● Live off";
    }
  }

  function connectStream() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${location.host}/v1/stream`;
    try {
      streamSocket = new WebSocket(url);
    } catch (err) {
      setLive("off");
      return;
    }
    streamSocket.addEventListener("open", () => setLive("on", "stream"));
    streamSocket.addEventListener("close", () => {
      setLive("off");
      setTimeout(connectStream, 4000);
    });
    streamSocket.addEventListener("error", () => setLive("off"));
    streamSocket.addEventListener("message", (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch { return; }
      if (msg.type === "heartbeat" || msg.type === "pong" || msg.type === "hello") return;
      if (msg.type === "ingest_progress") {
        const d = msg.detail || {};
        const label = d.drug ? `${msg.stage}: ${d.drug}` : msg.stage;
        statusLine.textContent = `Pulling · ${label}`;
        setLive("pulse", label);
        return;
      }
      if (msg.type === "ingest_complete") {
        const delta = msg.delta || {};
        const after = msg.after?.fused_pairs;
        statusLine.textContent = `Pull done · fused Δ${delta.fused_pairs ?? 0} · PV Δ${delta.pv_events ?? 0}`;
        if (after != null) countChip.textContent = `${after} pairs`;
        setLive("on", "updated");
        finishPullUi(true);
        bootCatalogAndQueue(after);
        return;
      }
      if (msg.type === "ingest_error") {
        statusLine.textContent = `Pull failed · ${msg.error || "error"}`;
        finishPullUi(false);
        return;
      }
      if (msg.type === "ledger_event") {
        streamEvents += 1;
        setLive("pulse", msg.summary || `#${msg.event_id}`);
        if (!pullAllBtn?.disabled) {
          statusLine.textContent = `Stream · ${msg.source || "ledger"} · ${msg.summary || msg.event_id}`;
        }
        setTimeout(() => setLive("on", `${streamEvents} evt`), 1200);
      }
    });
    setInterval(() => {
      if (streamSocket && streamSocket.readyState === WebSocket.OPEN) {
        streamSocket.send(JSON.stringify({ type: "ping" }));
      }
    }, 20000);
  }

  function finishPullUi(ok) {
    if (pullAllBtn) {
      pullAllBtn.disabled = false;
      pullAllBtn.textContent = "Pull all sources";
    if (cancelJobBtn) cancelJobBtn.classList.add("hidden");
    if (jobProgress) jobProgress.classList.add("hidden");
    activeJob = null;
    }
    if (pullPoll) {
      clearInterval(pullPoll);
      pullPoll = null;
    }
  }

  async function bootCatalogAndQueue(preferredTotal) {
    try {
      const cat = await fetch("/v1/catalog").then((r) => r.json());
      renderCatalog(cat);
      const fused = preferredTotal != null ? preferredTotal : cat.queue?.fused_pairs;
      await loadQueue(fused);
    } catch (err) {
      console.error(err);
    }
  }

  async function startPullAll() {
    if (!pullAllBtn || pullAllBtn.disabled) return;
    pullAllBtn.disabled = true;
    if (cancelJobBtn) cancelJobBtn.classList.remove("hidden");
    if (jobProgress) { jobProgress.classList.remove("hidden"); jobProgress.value = 0; }
    pullAllBtn.textContent = "Pulling…";
    statusLine.textContent = "Starting cumulative pull across all sources…";
    try {
      // faers_limit kept modest — pull still walks every MVP drug × FAERS/CT.gov/literature
      const res = await fetch("/v1/ingest/cumulative?live=true&faers_limit=8", { method: "POST" }).then((r) => r.json());
      if (res.mode === "sync") {
        const d = res.result?.delta || {};
        statusLine.textContent = `Pull done · fused Δ${d.fused_pairs ?? 0} · PV Δ${d.pv_events ?? 0}`;
        finishPullUi(true);
        await bootCatalogAndQueue();
        return;
      }
      const jobId = res.job_id;
      activeJob = jobId;
      statusLine.textContent = `Job ${jobId} queued · live APIs for all MVP drugs, then recompute…`;
      pullPoll = setInterval(async () => {
        try {
          const job = await fetch(`/v1/ingest/jobs/${jobId}`).then((r) => r.json());
          if (job.stage && job.status === "running") {
            const d = job.detail || {};
            if (jobProgress && d.n && d.i != null) {
              jobProgress.classList.remove("hidden");
              jobProgress.max = d.n;
              jobProgress.value = d.i;
            }
            statusLine.textContent = `Pulling · ${job.stage}${d.drug ? ": " + d.drug : ""}${d.i ? ` (${d.i}/${d.n})` : ""}${d.msg ? " · " + d.msg : ""}`;
          }
          if (job.status === "cancelled") {
            statusLine.textContent = "Pull cancelled by user";
            finishPullUi(false);
          }
          if (job.status === "done") {
            const delta = job.result?.delta || job.detail || {};
            const after = job.result?.after?.fused_pairs;
            statusLine.textContent =
              `Pull done · fused ${job.result?.before?.fused_pairs ?? "?"}→${after ?? "?"} ` +
              `(Δ${delta.fused_pairs ?? 0}) · PV Δ${delta.pv_events ?? 0} · refreshing list…`;
            if (after != null) countChip.textContent = `${after} pairs`;
            finishPullUi(true);
            await bootCatalogAndQueue(after);
          }
          if (job.status === "error") {
            statusLine.textContent = `Pull failed · ${job.error || "error"}`;
            finishPullUi(false);
          }
        } catch (err) {
          console.error(err);
        }
      }, 2000);
    } catch (err) {
      statusLine.textContent = `Pull failed · ${err}`;
      finishPullUi(false);
    }
  }

  if (pullAllBtn) pullAllBtn.addEventListener("click", () => startPullAll());
  if (cancelJobBtn) cancelJobBtn.addEventListener("click", async () => {
    if (!activeJob) return;
    try {
      await fetch(`/v1/ingest/jobs/${activeJob}/cancel`, { method: "POST" });
      statusLine.textContent = "Cancelling pull…";
    } catch (err) {
      statusLine.textContent = `Cancel failed: ${err.message}`;
    }
  });

  async function boot() {
    try {
      const health = await fetch("/health").then((r) => r.json());
      modelChip.textContent = health.model_version || "qslrm-v1.0.0";
      statusLine.textContent = "Hypothesis triage · ≠ causality · use Pull all sources to grow the queue";
      renderCatalog(await fetch("/v1/catalog").then((r) => r.json()));
      await loadQueue();
      connectStream();
    } catch (err) {
      body.innerHTML = `<tr><td colspan="12" class="empty">${esc(err)}</td></tr>`;
      statusLine.textContent = "API down";
    }
  }

  boot();
})();

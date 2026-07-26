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
  const sortBy = document.getElementById("sortBy");
  const themeToggle = document.getElementById("themeToggle");

  const liveChip = document.getElementById("liveChip");
  const pullAllBtn = document.getElementById("pullAllBtn");
  let items = [];
  let deep = null;
  let streamSocket = null;
  let streamEvents = 0;
  let pullPoll = null;

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

  function renderTabs(d) {
    document.getElementById("tab-decisions").innerHTML = (d.decisions || []).map((c) => `
      <div class="card kind-${esc(c.kind)}"><h3>${esc(c.title)}</h3><p>${esc(c.body)}</p></div>`
    ).join("") || `<p class="panel-note">No decisions.</p>`;

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
        <div><span class="k">ROR</span><span class="v">${fmt(d.ror)}</span></div>
        <div><span class="k">ΔROR</span><span class="v">${v ? fmt(v.delta_ror) : "—"}</span></div>
        <div><span class="k">Serious</span><span class="v">${pct(d.serious_rate)}</span></div>
      </div>
      <table class="mini-table"><thead><tr><th>Stratum</th><th>Value</th><th>Lift</th></tr></thead>
      <tbody>${(d.demographics || []).slice(0, 8).map((x) =>
        `<tr><td>${esc(x.stratum_type)}</td><td>${esc(x.stratum_value)}</td>
         <td class="mono">${x.lift_vs_background == null ? "—" : fmt(x.lift_vs_background)}</td></tr>`
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
      ${lit.map((p) => `
        <div class="lit-card ${p.matches_pair ? "match" : ""}">
          <div class="lit-meta">${esc(p.source)}${p.extractor ? ` · ${esc(p.extractor)}` : ""} · ${esc(p.pmid)}${p.year ? ` · ${p.year}` : ""}${p.citation_count != null ? ` · ${p.citation_count} cites` : ""}</div>
          <div class="lit-title">${esc(p.title)}</div>
          <p class="panel-note">${esc(p.snippet || "")}</p>
        </div>`
      ).join("") || `<p class="panel-note">No literature evidence.</p>`}`;

    document.getElementById("tab-protocol").innerHTML = (d.protocol_exclusions || []).map((p) => `
      <div class="clause">${esc(p.clause_text)}</div>
      <p class="panel-note">${esc(p.rationale)}</p>`
    ).join("") || `<p class="panel-note">No exclusion clause.</p>`;
  }

  async function selectRow(item, tr) {
    document.querySelectorAll("#queueBody tr").forEach((el) => el.classList.remove("active"));
    if (tr) tr.classList.add("active");
    drawerTitle.textContent = `${item.drug_name} ↔ ${item.pt_string}`;
    drawerSub.textContent = [item.sponsor_company, item.brand_name].filter(Boolean).join(" · ");
    setAttrs(item);
    openDrawer();
    try {
      deep = await fetch(`/v1/deep-dive/${encodeURIComponent(item.drug_id)}/${encodeURIComponent(item.ae_term_id)}`).then((r) => r.json());
      setAttrs(deep);
      renderTabs(deep);
    } catch (err) {
      document.getElementById("tab-decisions").innerHTML = `<p class="panel-note">${esc(err)}</p>`;
    }
  }

  async function loadQueue() {
    // Request full ranked set; chip uses API `total` (not page length)
    const params = new URLSearchParams({ limit: "2000", sort: sortBy.value || "fused" });
    if (searchBox.value.trim()) params.set("q", searchBox.value.trim());
    if (filterSponsor.value) params.set("sponsor", filterSponsor.value);
    if (filterMolecule.value) params.set("molecule_type", filterMolecule.value);
    if (filterRegion.value) params.set("region", filterRegion.value);
    params.set("sort", sortBy.value);
    const data = await fetch(`/v1/risk-scores?${params}`).then((r) => r.json());
    items = data.items || [];
    const total = Number(data.total != null ? data.total : items.length);
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
      tr.addEventListener("click", () => selectRow(item, tr));
      body.appendChild(tr);
    });
    selectRow(items[0], body.querySelector("tr"));
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
  }

  let debounce;
  const reload = () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => loadQueue().catch(console.error), 150);
  };
  [searchBox, filterSponsor, filterMolecule, filterRegion, sortBy].forEach((el) => {
    el.addEventListener("change", reload);
    el.addEventListener("input", reload);
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
        statusLine.textContent = `Pull done · fused Δ${delta.fused_pairs ?? 0} · PV Δ${delta.pv_events ?? 0}`;
        setLive("on", "updated");
        finishPullUi(true);
        bootCatalogAndQueue();
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
    }
    if (pullPoll) {
      clearInterval(pullPoll);
      pullPoll = null;
    }
  }

  async function bootCatalogAndQueue() {
    try {
      renderCatalog(await fetch("/v1/catalog").then((r) => r.json()));
      await loadQueue();
    } catch (err) {
      console.error(err);
    }
  }

  async function startPullAll() {
    if (!pullAllBtn || pullAllBtn.disabled) return;
    pullAllBtn.disabled = true;
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
      statusLine.textContent = `Job ${jobId} queued · live APIs for all MVP drugs, then recompute…`;
      pullPoll = setInterval(async () => {
        try {
          const job = await fetch(`/v1/ingest/jobs/${jobId}`).then((r) => r.json());
          if (job.stage && job.status === "running") {
            const d = job.detail || {};
            statusLine.textContent = `Pulling · ${job.stage}${d.drug ? ": " + d.drug : ""}${d.i ? ` (${d.i}/${d.n})` : ""}${d.msg ? " · " + d.msg : ""}`;
          }
          if (job.status === "done") {
            const delta = job.result?.delta || job.detail || {};
            statusLine.textContent =
              `Pull done · fused ${job.result?.before?.fused_pairs ?? "?"}→${job.result?.after?.fused_pairs ?? "?"} ` +
              `(Δ${delta.fused_pairs ?? 0}) · PV Δ${delta.pv_events ?? 0} · refreshing list…`;
            finishPullUi(true);
            await bootCatalogAndQueue();
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

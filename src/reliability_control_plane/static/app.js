const state = {
  overview: null,
  incidents: [],
  selectedIncidentId: null,
};

const elements = {
  riskScore: document.querySelector("#risk-score"),
  riskLabel: document.querySelector("#risk-label"),
  incidentCount: document.querySelector("#incident-count"),
  criticalCount: document.querySelector("#critical-count"),
  errorBudget: document.querySelector("#error-budget"),
  sloStatus: document.querySelector("#slo-status"),
  signalCount: document.querySelector("#signal-count"),
  serviceCount: document.querySelector("#service-count"),
  policyCount: document.querySelector("#policy-count"),
  incidentList: document.querySelector("#incident-list"),
  decisionContent: document.querySelector("#decision-content"),
  decisionScore: document.querySelector("#decision-score"),
  signalRows: document.querySelector("#signal-rows"),
  scenario: document.querySelector("#scenario"),
  runScenario: document.querySelector("#run-scenario"),
  reset: document.querySelector("#reset"),
  lastUpdated: document.querySelector("#last-updated"),
  sloObserved: document.querySelector("#slo-observed"),
  budgetRing: document.querySelector("#budget-ring"),
  budgetRingValue: document.querySelector("#budget-ring-value"),
  toast: document.querySelector("#toast"),
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function formatSignalValue(signal) {
  const value =
    typeof signal.value === "number" && !Number.isInteger(signal.value)
      ? signal.value.toFixed(2).replace(/\.?0+$/, "")
      : signal.value;
  return `${escapeHtml(value)}${signal.unit ? ` ${escapeHtml(signal.unit)}` : ""}`;
}

function riskLabel(score) {
  if (score >= 85) return "Immediate response";
  if (score >= 60) return "Action required";
  if (score >= 35) return "Needs attention";
  if (score > 0) return "Low exposure";
  return "Healthy baseline";
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("is-visible");
  window.setTimeout(() => elements.toast.classList.remove("is-visible"), 2600);
}

function renderOverview(overview) {
  state.overview = overview;
  state.incidents = overview.incidents;
  elements.riskScore.textContent = overview.risk_score;
  elements.riskLabel.textContent = riskLabel(overview.risk_score);
  elements.incidentCount.textContent = overview.open_incidents;
  elements.criticalCount.textContent = `${overview.critical_incidents} critical`;
  elements.errorBudget.textContent = `${overview.slo.error_budget_remaining_pct.toFixed(1)}%`;
  elements.sloStatus.textContent = `${overview.slo.state} · 99.9% SLO`;
  elements.signalCount.textContent = overview.signals_processed;
  elements.serviceCount.textContent = `${overview.services_observed} services`;
  elements.policyCount.textContent = `${overview.policy_rules} active policies`;
  elements.lastUpdated.textContent =
    `Updated ${formatTime(overview.generated_at)} · ${overview.signals_processed} signals evaluated`;
  elements.sloObserved.textContent = `${overview.slo.observed_pct.toFixed(3)}% observed`;
  elements.budgetRingValue.textContent =
    `${overview.slo.error_budget_remaining_pct.toFixed(0)}%`;
  elements.budgetRing.style.setProperty(
    "--budget",
    Math.max(0, Math.min(100, overview.slo.error_budget_remaining_pct)),
  );

  renderIncidentList();
  if (!state.selectedIncidentId || !state.incidents.some((item) => item.id === state.selectedIncidentId)) {
    state.selectedIncidentId = state.incidents[0]?.id ?? null;
  }
  renderDecision();
}

function renderIncidentList() {
  if (!state.incidents.length) {
    elements.incidentList.innerHTML =
      '<div class="empty-row">No policy violations are active. The current baseline is healthy.</div>';
    return;
  }

  elements.incidentList.innerHTML = state.incidents
    .map(
      (incident) => `
        <button
          class="incident-item severity-${escapeHtml(incident.severity)}
            ${incident.id === state.selectedIncidentId ? "is-active" : ""}"
          data-incident-id="${escapeHtml(incident.id)}"
          type="button"
          role="listitem"
        >
          <span class="severity-rail" aria-hidden="true"></span>
          <span class="incident-main">
            <strong>${escapeHtml(incident.title)}</strong>
            <span>${escapeHtml(incident.service)} · ${escapeHtml(incident.entity)} ·
              ${incident.violations.length} checks</span>
          </span>
          <span class="incident-score">
            <strong>${incident.score}</strong>
            <small>${escapeHtml(incident.severity)}</small>
          </span>
        </button>
      `,
    )
    .join("");

  elements.incidentList.querySelectorAll("[data-incident-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedIncidentId = button.dataset.incidentId;
      renderIncidentList();
      renderDecision();
    });
  });
}

function renderDecision() {
  const incident = state.incidents.find((item) => item.id === state.selectedIncidentId);
  if (!incident) {
    elements.decisionScore.textContent = "No active incident";
    elements.decisionContent.className = "empty-state";
    elements.decisionContent.innerHTML = `
      <i data-lucide="shield-check" aria-hidden="true"></i>
      <p>The control plane found no active policy violations in this scenario.</p>
    `;
    window.lucide?.createIcons();
    return;
  }

  elements.decisionScore.textContent = `${incident.score}/100 · ${incident.severity}`;
  elements.decisionContent.className = "decision-body";
  elements.decisionContent.innerHTML = `
    <p class="decision-summary">${escapeHtml(incident.summary)}</p>
    <div class="decision-block">
      <h3>Correlation trace</h3>
      <ul class="evidence-list">
        ${incident.violations
          .map(
            (violation) => `
              <li>
                <i>${escapeHtml(violation.kind.slice(0, 1).toUpperCase())}</i>
                <span><strong>${escapeHtml(violation.rule_title)}</strong><br />
                  ${escapeHtml(violation.signal_name)} = ${escapeHtml(violation.observed_value)}
                  · ${violation.evidence_count} samples</span>
              </li>
            `,
          )
          .join("")}
      </ul>
    </div>
    <div class="decision-block">
      <h3>Likely cause</h3>
      <p>${escapeHtml(incident.root_cause_hint)}</p>
    </div>
    <div class="decision-block">
      <h3>Recommended actions</h3>
      <ul class="action-list">
        ${incident.recommended_actions
          .map((action, index) => `<li><i>${index + 1}</i><span>${escapeHtml(action)}</span></li>`)
          .join("")}
      </ul>
    </div>
  `;
}

async function renderSignals() {
  const response = await fetch("/api/signals?limit=8");
  if (!response.ok) throw new Error("Could not load recent signals");
  const signals = await response.json();
  if (!signals.length) {
    elements.signalRows.innerHTML =
      '<div class="empty-row">Run a scenario to populate the evidence pipeline.</div>';
    return;
  }
  elements.signalRows.innerHTML = signals
    .map(
      (signal) => `
        <div class="table-row" role="row">
          <span role="cell">${formatTime(signal.timestamp)}</span>
          <span role="cell">${escapeHtml(signal.service)}</span>
          <span role="cell">
            <b class="signal-kind">${escapeHtml(signal.kind)}</b>
            ${escapeHtml(signal.name)}
          </span>
          <span role="cell">${formatSignalValue(signal)}</span>
        </div>
      `,
    )
    .join("");
}

async function refresh() {
  const response = await fetch("/api/overview");
  if (!response.ok) throw new Error("Could not load reliability overview");
  renderOverview(await response.json());
  await renderSignals();
  window.lucide?.createIcons();
}

async function post(url) {
  elements.runScenario.disabled = true;
  elements.reset.disabled = true;
  try {
    const response = await fetch(url, { method: "POST" });
    if (!response.ok) throw new Error(`Request failed with status ${response.status}`);
    renderOverview(await response.json());
    await renderSignals();
    window.lucide?.createIcons();
  } finally {
    elements.runScenario.disabled = false;
    elements.reset.disabled = false;
  }
}

elements.runScenario.addEventListener("click", async () => {
  try {
    await post(`/api/simulate/${encodeURIComponent(elements.scenario.value)}`);
    showToast(`Scenario loaded: ${elements.scenario.selectedOptions[0].textContent}`);
  } catch (error) {
    showToast(error.message);
  }
});

elements.reset.addEventListener("click", async () => {
  try {
    state.selectedIncidentId = null;
    await post("/api/reset");
    showToast("Telemetry and incidents cleared");
  } catch (error) {
    showToast(error.message);
  }
});

refresh().catch((error) => {
  showToast(error.message);
});

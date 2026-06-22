const state = {
  boot: null,
  activeJob: null,
  activeAnalysis: null,
};

const $ = (id) => document.getElementById(id);

function headers() {
  return {
    "Content-Type": "application/json",
  };
}

function showStatus(message, error = false) {
  const box = $("status");
  box.textContent = message;
  box.className = error ? "notice error" : "notice";
  window.setTimeout(() => box.classList.add("hidden"), 4200);
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Request failed");
  return payload;
}

async function bootstrap() {
  state.boot = await request("/api/bootstrap");
  render();
}

function render() {
  const boot = state.boot || {};
  const projects = boot.projects || [];
  const analyses = boot.analyses || [];
  const sources = boot.source_health?.source_health || [];
  const ready = sources.filter((item) => item.legal_ready).length;

  $("logout").classList.toggle("hidden", !boot.authenticated);
  $("metric-projects").textContent = projects.length;
  $("metric-analyses").textContent = analyses.length;
  $("metric-sources").textContent = `${ready}/${sources.length}`;
  renderProjects(projects);
  renderAnalyses(analyses);
  renderSources(sources);
  renderProjectSelect(projects);
  renderActionPlan(analyses[0]);
}

function renderProjects(projects) {
  const el = $("project-list");
  if (!projects.length) {
    el.className = "table empty";
    el.textContent = "No projects yet. Add one to start tracking public ASO data.";
    return;
  }
  el.className = "table";
  el.innerHTML = projects.map((project) => `
    <div class="row">
      <div><strong>${escapeHtml(project.name)}</strong><br><small>${escapeHtml(project.package_id)}</small></div>
      <div>${escapeHtml(project.category || "uncategorized")}<br><small>${escapeHtml(project.seed_text || "no seeds")}</small></div>
      <div>${escapeHtml(project.country)}/${escapeHtml(project.lang)}<br><small>${project.competitors.length} competitors</small></div>
      <span class="pill">active</span>
    </div>
  `).join("");
}

function renderAnalyses(analyses) {
  const el = $("recent-analyses");
  if (!analyses.length) {
    el.className = "list empty";
    el.textContent = "No analyses yet.";
    return;
  }
  el.className = "list";
  el.innerHTML = analyses.map((item) => `
    <div class="row">
      <div><strong>${escapeHtml(item.analysis_type)}</strong><br><small>${escapeHtml(item.created_at)}</small></div>
      <div>${escapeHtml(item.summary)}</div>
      <div><span class="pill">${escapeHtml(item.status)}</span></div>
      <button class="secondary" data-analysis="${item.id}">Open</button>
    </div>
  `).join("");
  el.querySelectorAll("[data-analysis]").forEach((button) => {
    button.addEventListener("click", () => openAnalysis(button.dataset.analysis));
  });
}

function renderActionPlan(analysis) {
  const el = $("action-plan");
  const actions = analysis?.action_plan || [];
  if (!actions.length) {
    el.className = "action-plan empty";
    el.textContent = "Create a project to generate an ASO action plan.";
    return;
  }
  el.className = "action-plan";
  el.innerHTML = `<div class="section-head"><h2>Next Best Actions</h2><span class="pill">${escapeHtml(analysis.analysis_type)}</span></div>` + actions.map((item) => `
    <article class="action-card">
      <span class="pill ${item.priority === "high" ? "warn" : ""}">${escapeHtml(item.priority)}</span>
      <strong>${escapeHtml(item.title)}</strong>
      <p>${escapeHtml(item.why)}</p>
    </article>
  `).join("");
}

function renderSources(sources) {
  const el = $("source-list");
  el.innerHTML = sources.map((source) => `
    <div class="row">
      <div><strong>${escapeHtml(source.source_id)}</strong><br><small>${escapeHtml(source.display_name)}</small></div>
      <div>${escapeHtml(source.policy_status)}</div>
      <div>${source.enabled ? "enabled" : "disabled"}</div>
      <span class="pill ${source.legal_ready ? "" : "warn"}">${source.legal_ready ? "ready" : "blocked"}</span>
    </div>
  `).join("");
}

function renderProjectSelect(projects) {
  $("project-select").innerHTML = projects.map((project) => `<option value="${project.id}">${escapeHtml(project.name)} - ${escapeHtml(project.package_id)}</option>`).join("");
}

function activeProjectId() {
  const value = $("project-select").value;
  if (!value) throw new Error("Create a project first.");
  return Number(value);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

document.querySelectorAll(".nav").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".view").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    $(button.dataset.view).classList.add("active");
  });
});

$("signin-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const email = $("email").value.trim();
    const workspace = $("workspace-name").value.trim();
    const start = await request("/api/auth/start", { method: "POST", headers: headers(), body: JSON.stringify({ email, workspace_name: workspace }) });
    if (!start.dev_token) throw new Error("Magic link created. Check email to continue.");
    await request("/api/auth/verify", { method: "POST", headers: headers(), body: JSON.stringify({ token: start.dev_token }) });
    await bootstrap();
    showStatus("Signed in. Workspace ready.");
  } catch (error) {
    showStatus(error.message, true);
  }
});

$("project-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const payload = {
      name: $("project-name").value,
      package_id: $("package-id").value,
      category: $("category").value,
      seed_text: $("seed-text").value,
      competitors: $("competitors").value,
    };
    const market = $("market").value.trim().toLowerCase();
    if (market.includes("-")) {
      const [lang, country] = market.split("-");
      payload.lang = lang;
      payload.country = country;
    }
    const result = await request("/api/projects", { method: "POST", headers: headers(), body: JSON.stringify(payload) });
    event.target.reset();
    await bootstrap();
    if (result.job) pollJob(result.job.id);
    showStatus("Project created. First audit queued.");
  } catch (error) {
    showStatus(error.message, true);
  }
});

$("keyword-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const payload = { keywords: $("keyword-list").value, app_text: $("app-text").value };
    const result = await request("/api/keywords/score", { method: "POST", headers: headers(), body: JSON.stringify(payload) });
    showAnalysis(result.analysis);
    await bootstrap();
    showStatus("Keyword score saved.");
  } catch (error) {
    showStatus(error.message, true);
  }
});

$("run-baseline").addEventListener("click", async () => {
  try {
    $("analysis-output").textContent = "Queued baseline. Polling job status.";
    const result = await request(`/api/projects/${activeProjectId()}/analyses?analysis_type=baseline`, { method: "POST", headers: headers(), body: "{}" });
    pollJob(result.job.id);
    await bootstrap();
    showStatus("Baseline queued.");
  } catch (error) {
    showStatus(error.message, true);
  }
});

$("run-metadata").addEventListener("click", async () => {
  try {
    const result = await request(`/api/projects/${activeProjectId()}/analyses?analysis_type=metadata`, { method: "POST", headers: headers(), body: "{}" });
    pollJob(result.job.id);
    await bootstrap();
    showStatus("Metadata audit queued.");
  } catch (error) {
    showStatus(error.message, true);
  }
});

$("refresh").addEventListener("click", bootstrap);
$("logout").addEventListener("click", async () => {
  await request("/api/logout", { method: "POST", headers: headers(), body: "{}" });
  state.boot = null;
  state.activeAnalysis = null;
  $("analysis-output").textContent = "Signed out.";
  $("report-links").classList.add("hidden");
  await bootstrap();
});

async function pollJob(jobId) {
  state.activeJob = jobId;
  $("analysis-output").textContent = `Job ${jobId}: queued`;
  for (let attempt = 0; attempt < 120; attempt++) {
    const result = await request(`/api/analysis-jobs/${jobId}`);
    const job = result.job;
    $("analysis-output").textContent = `Job ${job.id}: ${job.status}${job.error_message ? "\n" + job.error_message + "\nFix: " + job.error_fix : ""}`;
    if (job.status === "succeeded") {
      await openAnalysis(job.analysis_id);
      await bootstrap();
      showStatus("Analysis complete.");
      return;
    }
    if (job.status === "failed") {
      await bootstrap();
      showStatus(job.error_message || "Analysis failed.", true);
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
  showStatus("Analysis still running. Refresh later.", true);
}

async function openAnalysis(id) {
  if (!id) return;
  const result = await request(`/api/analyses/${id}`);
  showAnalysis(result.analysis);
}

function showAnalysis(analysis) {
  state.activeAnalysis = analysis;
  $("analysis-output").textContent = JSON.stringify(analysis.payload, null, 2);
  renderActionPlan(analysis);
  const links = $("report-links");
  links.classList.remove("hidden");
  links.innerHTML = `
    <a href="/api/reports/${analysis.id}.md" target="_blank">Markdown report</a>
    <a href="/api/reports/${analysis.id}.json" target="_blank">JSON evidence</a>
    <a href="/api/reports/${analysis.id}.csv" target="_blank">CSV table</a>
  `;
}

bootstrap().catch((error) => showStatus(error.message, true));

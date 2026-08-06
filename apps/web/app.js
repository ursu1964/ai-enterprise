const manifestInput = document.getElementById("manifestInput");
const statusLine = document.getElementById("statusLine");
const reviewState = document.getElementById("reviewState");
const reviewContent = document.getElementById("reviewContent");
const metrics = document.getElementById("metrics");
const importButton = document.getElementById("importButton");
const approveButton = document.getElementById("approveButton");
const correctButton = document.getElementById("correctButton");
const answerButton = document.getElementById("answerButton");
const downloadButton = document.getElementById("downloadButton");
const loadSampleButton = document.getElementById("loadSampleButton");
const answerInput = document.getElementById("answerInput");
const roleSelect = document.getElementById("roleSelect");
const deviceSelect = document.getElementById("deviceSelect");
const bootstrapExperienceButton = document.getElementById("bootstrapExperienceButton");
const refreshExperienceButton = document.getElementById("refreshExperienceButton");
const realtimeState = document.getElementById("realtimeState");
const experienceMetrics = document.getElementById("experienceMetrics");
const experienceRecords = document.getElementById("experienceRecords");
const surfaceContent = document.getElementById("surfaceContent");
const proposalInput = document.getElementById("proposalInput");
const commentInput = document.getElementById("commentInput");
const createProposalButton = document.getElementById("createProposalButton");
const createCollaborationButton = document.getElementById("createCollaborationButton");

let currentProjectId = null;
let currentManifest = null;
let currentDownloadUrl = null;
let currentClarificationReport = null;
let experiencePoll = null;
let experienceEvents = null;
const experienceChannel = "BroadcastChannel" in window
  ? new BroadcastChannel("ai-enterprise-r10-experience")
  : null;

const actorHeaders = {
  "Content-Type": "application/json",
  "X-Actor-ID": "client-portal-reviewer",
  "X-Actor-Type": "human",
  "X-Actor-Role": "platform-admin"
};

function setStatus(message, error = false) {
  statusLine.textContent = message;
  statusLine.classList.toggle("error", error);
}

function setRealtimeState(message, error = false) {
  realtimeState.textContent = message;
  realtimeState.classList.toggle("error", error);
}

function renderMetrics(payload) {
  metrics.innerHTML = [
    [payload.canonical_object_count || 0, "objects"],
    [payload.relationship_count || 0, "relationships"],
    [(payload.artifacts || []).length, "artifacts"]
  ].map(([value, label]) => `<div><strong>${value}</strong><span>${label}</span></div>`).join("");
}

function item(title, detail, meta = "") {
  return `<div class="item"><strong>${title}</strong><span>${detail}</span>${meta ? `<p>${meta}</p>` : ""}</div>`;
}

function apiUrl(path) {
  return `/api/v1/projects/${currentProjectId}/ueif/${path}`;
}

async function apiJson(path, options = {}) {
  const response = await fetch(apiUrl(path), {
    ...options,
    headers: actorHeaders
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(JSON.stringify(payload.detail || payload));
  }
  return payload;
}

function enableExperienceRuntime() {
  const enabled = Boolean(currentProjectId);
  bootstrapExperienceButton.disabled = !enabled;
  refreshExperienceButton.disabled = !enabled;
  createProposalButton.disabled = !enabled;
  createCollaborationButton.disabled = !enabled;
}

function broadcastExperienceUpdate(reason) {
  if (experienceChannel) {
    experienceChannel.postMessage({
      reason,
      project_id: currentProjectId,
      at: new Date().toISOString()
    });
  }
}

function startExperiencePolling() {
  if (experiencePoll) {
    clearInterval(experiencePoll);
  }
  experiencePoll = window.setInterval(() => {
    if (currentProjectId) {
      refreshExperienceState("poll").catch(() => setRealtimeState("poll failed", true));
    }
  }, 15000);
}

function startExperienceEventStream() {
  if (experienceEvents) {
    experienceEvents.close();
    experienceEvents = null;
  }
  if (!currentProjectId || !("EventSource" in window)) {
    return;
  }
  experienceEvents = new EventSource(apiUrl("events"));
  experienceEvents.addEventListener("open", () => setRealtimeState("stream live"));
  experienceEvents.addEventListener("snapshot", (event) => {
    const payload = JSON.parse(event.data);
    renderExperienceRecords(payload.records || []);
    setRealtimeState(`stream · ${payload.record_count || 0} records`);
  });
  experienceEvents.addEventListener("heartbeat", () => setRealtimeState("stream heartbeat"));
  experienceEvents.addEventListener("error", () => {
    setRealtimeState("stream fallback", true);
    if (experienceEvents) {
      experienceEvents.close();
      experienceEvents = null;
    }
  });
}

function renderExperienceDashboard(payload) {
  experienceMetrics.innerHTML = [
    [payload.workspace_count || 0, "workspaces"],
    [payload.workspace_surface_count || 0, "surfaces"],
    [payload.collaboration_thread_count || 0, "collaboration"],
    [payload.ai_proposal_count || 0, "AI proposals"],
    [payload.experience_api_contract_count || 0, "API contracts"],
    [payload.notification_rule_count || 0, "notifications"]
  ].map(([value, label]) => `<div><strong>${value}</strong><span>${label}</span></div>`).join("");
}

function renderExperienceRecords(records) {
  if (!records.length) {
    experienceRecords.innerHTML = "No R10 records exist yet. Bootstrap the role workspace.";
    return;
  }
  experienceRecords.innerHTML = records.slice(-12).reverse().map((record) => item(
    `${record.record_type} · ${record.record_id}`,
    record.status,
    [record.role, record.object_ref, record.record_hash.slice(0, 12)].filter(Boolean).join(" · ")
  )).join("");
  const surfaces = records.filter((record) => record.record_type === "workspace_surface");
  surfaceContent.innerHTML = surfaces.length
    ? surfaces.map((record) => item(
      record.record_document.surface_type,
      record.record_document.visible_object_refs.join(" | "),
      record.record_document.source_system_refs.join(" | ")
    )).join("")
    : [
      item("Generation", "No generation surface recorded."),
      item("Runtime", "No runtime surface recorded."),
      item("Governance", "No governance surface recorded.")
    ].join("");
}

async function refreshExperienceState(reason = "manual") {
  if (!currentProjectId) {
    setRealtimeState("waiting");
    return;
  }
  setRealtimeState(reason === "poll" ? "polling" : "refreshing");
  const [dashboard, records] = await Promise.all([
    apiJson("dashboard"),
    apiJson("records")
  ]);
  renderExperienceDashboard(dashboard);
  renderExperienceRecords(records);
  setRealtimeState(`live · ${records.length} records`);
}

async function postExperienceRecord(path, body = null) {
  const options = { method: "POST" };
  if (body !== null) {
    options.body = JSON.stringify(body);
  }
  const payload = await apiJson(path, options);
  broadcastExperienceUpdate(path);
  await refreshExperienceState("write");
  return payload;
}

async function bootstrapExperienceRuntime() {
  if (!currentProjectId) {
    setStatus("Import a manifest before bootstrapping R10.", true);
    return;
  }
  setStatus("Bootstrapping R10 role experience runtime.");
  const role = roleSelect.value;
  const device = deviceSelect.value;
  const manifestRef = "manifest:current";
  const objectRef = "manifest_object:current";
  await postExperienceRecord("role-workspaces", { manifest_ref: manifestRef, role });
  await postExperienceRecord("experience-profiles", {
    user_ref: "client-portal-reviewer",
    role,
    device,
    personalization: { density: "comfortable", theme: "dark" }
  });
  await Promise.all([
    postExperienceRecord("workspace-surfaces", {
      surface_type: "generation",
      role,
      visible_object_refs: ["artifact:documentation", "artifact:api", "artifact:test-suite"],
      source_system_refs: ["artifact:generation-queue", manifestRef]
    }),
    postExperienceRecord("workspace-surfaces", {
      surface_type: "runtime",
      role,
      visible_object_refs: ["deployment:current", "runtime:health", "incident:open"],
      source_system_refs: [manifestRef, "runtime:current"]
    }),
    postExperienceRecord("workspace-surfaces", {
      surface_type: "governance",
      role,
      visible_object_refs: ["approval:pending", "risk:current", "audit:timeline"],
      source_system_refs: ["governance:current", manifestRef]
    })
  ]);
  await postExperienceRecord("ai-interaction-policies");
  await postExperienceRecord("experience-api-contracts", {
    platform_api_refs: [
      "/api/v1/projects/{project_id}/ueif/records",
      "/api/v1/projects/{project_id}/ueif/dashboard",
      "/api/v1/projects/{project_id}/ueif/ai-proposals"
    ]
  });
  await postExperienceRecord("notification-rules", {
    event_type: "approval.requested",
    role,
    object_ref: objectRef,
    delivery_channels: [device]
  });
  setStatus("R10 role experience runtime is active.");
}

async function createAiProposal() {
  if (!currentProjectId) {
    setStatus("Import a manifest before creating an AI proposal.", true);
    return;
  }
  await postExperienceRecord("ai-proposals", {
    ai_session_ref: "ai-session:client-portal",
    manifest_ref: "manifest:current",
    recommendation: proposalInput.value.trim() || "Review generated artifacts.",
    impact_analysis_ref: "impact:client-portal",
    validation_ref: "validation:client-portal"
  });
  setStatus("AI proposal recorded for human review.");
}

async function createCollaborationThread() {
  if (!currentProjectId) {
    setStatus("Import a manifest before recording collaboration.", true);
    return;
  }
  await postExperienceRecord("collaboration-threads", {
    manifest_object_ref: "manifest_object:current",
    comments: [commentInput.value.trim() || "Review note anchored to the Manifest."],
    review_refs: ["review:client-portal"],
    assignment_refs: ["assignment:current-role"],
    notification_refs: ["notification:role-aware"]
  });
  setStatus("Collaboration thread recorded and broadcast to open clients.");
}

function renderReview(payload) {
  reviewState.textContent = payload.review_state || payload.status || "ready";
  currentClarificationReport = payload.clarification_report || null;
  renderMetrics(payload);
  const missing = payload.missing_information || [];
  const assumptions = payload.assumptions || [];
  const objects = payload.canonical_model?.objects || [];
  const artifacts = payload.artifacts || [];
  const proof = payload.proof || {};
  reviewContent.innerHTML = [
    item("R1 proof", proof.ready ? "Ready" : "Needs review", proof.schema_version || ""),
    item("Next action", payload.next_action || "Review the generated blueprint."),
    item("Source manifest", payload.source_manifest_sha256 || "waiting", proof.source_object?.object_key || ""),
    item("Traceability", proof.traceability_manifest_sha256 || "waiting", `${proof.section_trace_count || 0} section traces`),
    item("Missing information", missing.length ? missing.join(" | ") : "No blocking missing information."),
    item("Assumptions", assumptions.length ? assumptions.join(" | ") : "No unresolved assumptions."),
    ...objects.slice(0, 8).map((object) => item(`${object.id} ${object.type}`, object.name, object.status)),
    ...artifacts.map((artifact) => item(artifact.artifact_type, artifact.content_hash, artifact.download_url || "stored"))
  ].join("");
  renderAnswerTemplate(payload);
}

function clarificationQuestions(report) {
  if (!report) {
    return [];
  }
  return [
    ...(report.critical_blockers || []),
    ...(report.important_ambiguities || []),
    ...(report.unverified_assumptions || []),
    ...(report.recommended_improvements || []),
    ...(report.optional_enhancements || [])
  ];
}

function renderAnswerTemplate(payload) {
  const questions = clarificationQuestions(payload.clarification_report);
  if (!questions.length) {
    answerInput.value = "";
    answerInput.placeholder = "No clarification questions are open for this blueprint.";
    answerButton.disabled = true;
    return;
  }
  answerInput.placeholder = "Edit responses, rationale, and optional scoped corrections.";
  answerInput.value = JSON.stringify(questions.map((question) => ({
    question_id: question.id,
    response: "",
    resolution: "answered",
    rationale: "",
    corrections: []
  })), null, 2);
  answerButton.disabled = false;
}

function manifestRequestBody(text, correction = false) {
  try {
    const manifest = JSON.parse(text);
    return correction
      ? { corrected_manifest: manifest }
      : { manifest };
  } catch (_) {
    return correction
      ? { corrected_manifest_text: text, content_type: "application/yaml" }
      : { manifest_text: text, content_type: "application/yaml" };
  }
}

async function loadSampleManifest() {
  const response = await fetch("/dashboard/sample-project-manifest");
  if (!response.ok) {
    setStatus("Sample manifest is unavailable.", true);
    return;
  }
  currentManifest = await response.json();
  manifestInput.value = JSON.stringify(currentManifest, null, 2);
  setStatus("Sample manifest loaded.");
}

async function importManifest() {
  const requestBody = manifestRequestBody(manifestInput.value);
  setStatus("Importing manifest.");
  const response = await fetch("/api/v1/project-formation/client-blueprints/import", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Actor-ID": "client-portal-reviewer",
      "X-Actor-Type": "human",
      "X-Actor-Role": "platform-admin"
    },
    body: JSON.stringify(requestBody)
  });
  const payload = await response.json();
  if (!response.ok) {
    setStatus(`Import failed: ${JSON.stringify(payload.detail || payload)}`, true);
    return;
  }
  currentProjectId = payload.project_id;
  currentManifest = requestBody.manifest || requestBody.manifest_text;
  currentDownloadUrl = payload.blueprint_download_url;
  renderReview(payload);
  approveButton.disabled = false;
  correctButton.disabled = false;
  downloadButton.disabled = !currentDownloadUrl;
  enableExperienceRuntime();
  startExperiencePolling();
  startExperienceEventStream();
  await refreshExperienceState("import");
  setStatus("Manifest imported. Review the canonical blueprint before approval.");
}

async function approveBlueprint() {
  if (!currentProjectId || !currentManifest) {
    setStatus("Import a manifest before approval.", true);
    return;
  }
  setStatus("Recording approval.");
  const response = await fetch(`/api/v1/project-formation/client-blueprints/${currentProjectId}/review`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Actor-ID": "client-portal-reviewer",
      "X-Actor-Type": "human",
      "X-Actor-Role": "platform-admin"
    },
    body: JSON.stringify({
      decision: "approved",
      reviewer_comment: "Approved from the client portal."
    })
  });
  const payload = await response.json();
  if (!response.ok) {
    setStatus(`Approval failed: ${JSON.stringify(payload.detail || payload)}`, true);
    return;
  }
  currentDownloadUrl = payload.blueprint_download_url;
  renderReview(payload);
  downloadButton.disabled = !currentDownloadUrl;
  answerButton.disabled = !clarificationQuestions(payload.clarification_report).length;
  setStatus("Blueprint approved and ready to download.");
}

async function submitClarificationAnswers() {
  if (!currentProjectId || !currentClarificationReport) {
    setStatus("Import a manifest with clarification questions before submitting answers.", true);
    return;
  }
  let answers = null;
  try {
    answers = JSON.parse(answerInput.value);
  } catch (_) {
    setStatus("Clarification answers must be a JSON array.", true);
    return;
  }
  if (!Array.isArray(answers) || !answers.length) {
    setStatus("Clarification answers must contain at least one answer.", true);
    return;
  }
  setStatus("Submitting clarification answers.");
  const response = await fetch(`/api/v1/project-formation/client-blueprints/${currentProjectId}/clarifications/answers`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Actor-ID": "client-portal-reviewer",
      "X-Actor-Type": "human",
      "X-Actor-Role": "platform-admin"
    },
    body: JSON.stringify({
      clarification_report: currentClarificationReport,
      answers
    })
  });
  const payload = await response.json();
  if (!response.ok) {
    setStatus(`Clarification answers failed: ${JSON.stringify(payload.detail || payload)}`, true);
    return;
  }
  currentDownloadUrl = payload.blueprint_download_url;
  renderReview(payload);
  approveButton.disabled = false;
  correctButton.disabled = false;
  downloadButton.disabled = !currentDownloadUrl;
  setStatus("Clarification answers submitted. Review the regenerated blueprint.");
}

async function submitCorrections() {
  if (!currentProjectId) {
    setStatus("Import a manifest before submitting corrections.", true);
    return;
  }
  const correctionBody = manifestRequestBody(manifestInput.value, true);
  setStatus("Submitting corrected manifest.");
  const response = await fetch(`/api/v1/project-formation/client-blueprints/${currentProjectId}/review`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Actor-ID": "client-portal-reviewer",
      "X-Actor-Type": "human",
      "X-Actor-Role": "platform-admin"
    },
    body: JSON.stringify({
      decision: "changes_requested",
      reviewer_comment: "Corrected manifest submitted from the client portal.",
      ...correctionBody
    })
  });
  const payload = await response.json();
  if (!response.ok) {
    setStatus(`Correction failed: ${JSON.stringify(payload.detail || payload)}`, true);
    return;
  }
  currentManifest = correctionBody.corrected_manifest || correctionBody.corrected_manifest_text;
  currentDownloadUrl = payload.blueprint_download_url;
  renderReview(payload);
  approveButton.disabled = false;
  downloadButton.disabled = !currentDownloadUrl;
  answerButton.disabled = !clarificationQuestions(payload.clarification_report).length;
  setStatus("Corrections submitted. Review the updated canonical blueprint before approval.");
}

function downloadBlueprint() {
  if (!currentDownloadUrl) {
    setStatus("No blueprint download is available yet.", true);
    return;
  }
  window.location.href = currentDownloadUrl;
}

loadSampleButton.addEventListener("click", loadSampleManifest);
importButton.addEventListener("click", importManifest);
approveButton.addEventListener("click", approveBlueprint);
correctButton.addEventListener("click", submitCorrections);
answerButton.addEventListener("click", submitClarificationAnswers);
downloadButton.addEventListener("click", downloadBlueprint);
bootstrapExperienceButton.addEventListener("click", bootstrapExperienceRuntime);
refreshExperienceButton.addEventListener("click", () => refreshExperienceState("manual"));
createProposalButton.addEventListener("click", createAiProposal);
createCollaborationButton.addEventListener("click", createCollaborationThread);
roleSelect.addEventListener("change", () => {
  if (currentProjectId) {
    broadcastExperienceUpdate("role-change");
  }
});

if (experienceChannel) {
  experienceChannel.addEventListener("message", (event) => {
    if (event.data?.project_id === currentProjectId) {
      refreshExperienceState("broadcast").catch(() => setRealtimeState("sync failed", true));
    }
  });
}

loadSampleManifest();

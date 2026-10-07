"use strict";
const $ = id => document.getElementById(id);
let review = null;
let selectedContact = "";
let busy = false;
let memoryItems = [];
let memoryItem = null;
let memoryBaseline = "";

function notice(text, error = false) {
  $("notice").textContent = text;
  $("notice").dataset.error = String(error);
}
function dirty() { return review && $("draft").value !== review.text; }
function controls() {
  document.querySelectorAll("input,select,textarea,button").forEach(el => { el.disabled = busy; });
  $("record").disabled = busy || Boolean(dirty());
  $("decision").querySelector('[value="usable"]').disabled = Boolean(review && !review.context_current);
  $("memory-kind").disabled = busy || Boolean(memoryItem);
  $("memory-save").disabled = busy || Boolean(memoryItem && memoryItem.status === "revoked") || (!memoryItem && (!review || !review.context_current));
  $("memory-withdraw").disabled = busy || !memoryItem || memoryItem.status === "revoked";
}
async function perform(action) {
  if (busy) return;
  busy = true; controls();
  try { await action(); } catch (error) { notice(error.message, true); }
  finally { busy = false; controls(); }
}
async function api(path, payload) {
  const response = await fetch(path, { method: payload === undefined ? "GET" : "POST",
    headers: { Authorization: `Bearer ${globalThis.reviewToken}`, "Content-Type": "application/json" },
    body: payload === undefined ? undefined : JSON.stringify(payload), cache: "no-store" });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Local review request failed");
  return result;
}
function addText(parent, tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  parent.append(node);
  return node;
}
function evidence(items, container, styles = false) {
  container.replaceChildren();
  if (!items.length) addText(container, "p", "No context in this view.", "muted");
  for (const item of items) {
    const section = document.createElement("section"); section.className = "source";
    const citation = !styles && review.original.citations.find(entry => entry.evidence_key === item.key);
    addText(section, "h3", styles ? `${item.source} · ${item.timestamp}` : `${citation ? "["+citation.label+"] " : ""}${item.key} · ${item.kind}`);
    addText(section, "p", styles ? item.body : item.text, "snippet");
    const details = document.createElement("details");
    addText(details, "summary", "Inspect provenance");
    addText(details, "pre", JSON.stringify(styles ? item : item.provenance, null, 2));
    section.append(details); container.append(section);
  }
}
function render(result) {
  review = result;
  $("workspace").hidden = false;
  $("contact").value = result.contact; selectedContact = result.contact;
  const request = result.original.packet.request;
  $("topic").value = request.query; $("cutoff").value = request.before; $("mode").value = request.mode;
  $("draft").value = result.text; $("original").textContent = result.original.draft_text;
  $("review-state").textContent = `Saved revision ${result.revision} · ${result.context_current ? "context unchanged" : "context changed — rebuild before marking usable"}`;
  $("review-notes").replaceChildren();
  result.original.review_notes.forEach(text => addText($("review-notes"), "li", text));
  evidence(result.original.packet.evidence, $("evidence"));
  evidence(result.original.packet.style_examples, $("examples"), true);
  $("decision").value = "needs_work"; $("retrieval").value = "not_rated"; $("style").value = "not_rated";
  $("feedback-notes").value = "";
  $("feedback-history").replaceChildren();
  for (const item of result.feedback || []) {
    addText($("feedback-history"), "p", `Revision ${item.revision}: ${item.decision} · ${item.retrieval} · ${item.style}${item.notes ? " — "+item.notes : ""}`, "muted");
  }
}
async function refreshContact() {
  const contact = $("contact").value;
  if (!contact) return;
  const saved = await api(`/api/reviews?contact=${encodeURIComponent(contact)}`);
  $("saved").replaceChildren();
  const placeholder = addText($("saved"), "option", "Choose a saved review"); placeholder.value = "";
  saved.forEach(item => { const option = addText($("saved"), "option", item.created_at); option.value = item.review_id; });
  if (review) $("saved").value = review.review_id;
  const stats = await api(`/api/summary?contact=${encodeURIComponent(contact)}`);
  $("metrics").textContent = `${stats.reviews} saved · ${stats.rated_current_revisions} current revisions rated · ${stats.changed_drafts} edited. Decisions: ${JSON.stringify(stats.decisions)}. ${stats.metric_note}`;
  await refreshMemory();
}
async function load(id) {
  const result = await api(`/api/reviews/${encodeURIComponent(id)}`);
  render(result);
  const history = await api(`/api/reviews/${encodeURIComponent(id)}/history`);
  $("history").replaceChildren();
  history.forEach(item => {
    const details = document.createElement("details");
    addText(details, "summary", `Revision ${item.revision} · ${item.saved_at}`);
    addText(details, "pre", item.text); $("history").append(details);
  });
  await refreshContact();
}
function memoryValues() {
  return { kind: $("memory-kind").value, text: $("memory-text").value, reason: $("memory-reason").value,
    sources: [...document.querySelectorAll("#memory-sources input:checked")].map(el => JSON.parse(el.value)) };
}
function memoryDirty() { return memoryBaseline && JSON.stringify(memoryValues()) !== memoryBaseline; }
function discardAllowed(includeMemory = false) {
  return (!dirty() && (!includeMemory || !memoryDirty())) || window.confirm(includeMemory ? "Discard unsaved draft or memory wording?" : "Discard unsaved draft wording?");
}
$("create-form").addEventListener("submit", event => {
  event.preventDefault(); if (!discardAllowed()) return;
  perform(async () => {
    const result = await api("/api/reviews", { contact: $("contact").value, before: $("cutoff").value,
      query: $("topic").value, mode: $("mode").value });
    if (result.status === "needs_history") { notice("No matching history. Try another topic, import messages, or select the generic template.", true); return; }
    await load(result.review_id); notice("Review saved. Inspect the sources and edit your reply.");
  });
});
$("contact").addEventListener("change", () => {
  if (!discardAllowed(true)) { $("contact").value = selectedContact; return; }
  selectedContact = $("contact").value; review = null; memoryItem = null; memoryBaseline = ""; $("workspace").hidden = true;
  perform(async () => { await refreshContact(); notice("Choose a topic or open a saved review."); });
});
$("load").addEventListener("click", () => {
  if (!discardAllowed()) return;
  perform(async () => { if (!$("saved").value) throw new Error("Choose a saved review first"); await load($("saved").value); notice("Saved review reopened."); });
});
$("draft").addEventListener("input", () => { controls(); notice(dirty() ? "Unsaved wording — save before rating." : "Wording matches the saved revision."); });
$("save").addEventListener("click", () => perform(async () => {
  await api(`/api/reviews/${review.review_id}/edit`, { expected_revision: review.revision, text: $("draft").value });
  await load(review.review_id); notice("Wording saved.");
}));
$("feedback-form").addEventListener("submit", event => {
  event.preventDefault(); perform(async () => {
    if (dirty()) throw new Error("Save wording before recording feedback");
    await api(`/api/reviews/${review.review_id}/feedback`, { expected_revision: review.revision,
      decision: $("decision").value, retrieval: $("retrieval").value, style: $("style").value, notes: $("feedback-notes").value });
    await load(review.review_id); notice("Feedback recorded for the saved wording.");
  });
});
window.addEventListener("beforeunload", event => { if (dirty() || memoryDirty()) { event.preventDefault(); event.returnValue = ""; } });

function renderMemory(item) {
  memoryItem = item;
  $("memory-select").value = item ? item.memory_id : "";
  $("memory-kind").value = item ? item.kind : "fact";
  $("memory-text").value = item ? item.text || "" : "";
  $("memory-reason").value = "";
  $("memory-state").textContent = item ? `Revision ${item.revision} · ${item.status} · ${item.eligible_at_cutoff ? "cutoff uses revision "+item.context_revision : "excluded at draft cutoff"}` : "New memory: choose citations from the draft's historical messages.";
  const sources = new Map();
  for (const entry of review ? review.original.packet.evidence : []) {
    if (entry.kind === "message") {
      const p = entry.provenance; sources.set(JSON.stringify([p.source, p.id]), { body: entry.text, source:p.source, id:p.id });
    }
  }
  if (item) for (const source of item.source_messages) {
    if (source.message) sources.set(JSON.stringify([source.source, source.message_id]), source.message);
  }
  const checked = new Set(item ? item.sources.map(ref => JSON.stringify([ref.source, ref.message_id])) : []);
  $("memory-sources").replaceChildren();
  if (!sources.size) addText($("memory-sources"), "p", "Create a draft with matching history to choose sources.", "muted");
  for (const [key, source] of sources) {
    const label = document.createElement("label"); label.className = "source-choice";
    const checkbox = document.createElement("input"); checkbox.type = "checkbox"; checkbox.value = key; checkbox.checked = checked.has(key);
    label.append(checkbox, document.createTextNode(`${source.source} / ${source.id}: ${source.body}`));
    $("memory-sources").append(label);
  }
  $("memory-history").replaceChildren();
  if (item) for (const revision of item.history) {
    const details = document.createElement("details");
    addText(details, "summary", `Revision ${revision.revision} · ${revision.status} · ${revision.effective_at}`);
    addText(details, "p", revision.text || "Withdrawn"); addText(details, "p", revision.reason, "muted");
    for (const source of revision.source_messages) {
      addText(details, "p", `${source.source} / ${source.message_id} · ${source.current ? "source unchanged" : "source missing, changed, or unavailable"}`, "muted");
      if (source.message) addText(details, "pre", source.message.body);
    }
    $("memory-history").append(details);
  }
  memoryBaseline = JSON.stringify(memoryValues()); controls();
}
async function refreshMemory() {
  const preserve = memoryDirty();
  const selected = memoryItem ? memoryItem.memory_id : "";
  memoryItems = await api(`/api/memory?contact=${encodeURIComponent($("contact").value)}&before=${encodeURIComponent($("cutoff").value)}`);
  $("memory-select").replaceChildren();
  addText($("memory-select"), "option", "New reviewed memory").value = "";
  for (const item of memoryItems) {
    addText($("memory-select"), "option", `${item.kind} · ${item.status} · ${(item.text || "Withdrawn").slice(0, 70)}`).value = item.memory_id;
  }
  if (preserve) { $("memory-select").value = selected; return; }
  renderMemory(memoryItems.find(item => item.memory_id === selected) || null);
}
$("memory-select").addEventListener("change", () => {
  if (memoryDirty() && !window.confirm("Discard unsaved memory wording?")) { $("memory-select").value = memoryItem ? memoryItem.memory_id : ""; return; }
  renderMemory(memoryItems.find(item => item.memory_id === $("memory-select").value) || null);
});
async function afterMemory(item) {
  memoryBaseline = ""; memoryItem = item;
  await refreshMemory();
  if (review) {
    const current = await api(`/api/reviews/${review.review_id}`);
    review.context_current = current.context_current;
    $("review-state").textContent = current.revision !== review.revision ? "Review changed in another editor — reopen before saving or rating." : `Saved revision ${review.revision} · ${current.context_current ? "context unchanged" : "context changed — rebuild before marking usable"}`;
  }
  notice("Memory saved. Use a cutoff after its revision time and rebuild to use the change.");
}
$("memory-form").addEventListener("submit", event => {
  event.preventDefault(); perform(async () => {
    const values = memoryValues();
    let item;
    if (memoryItem) {
      const { kind, ...payload } = values;
      item = await api(`/api/memory/${memoryItem.memory_id}/edit`, { ...payload, expected_revision: memoryItem.revision });
    } else {
      if (!review || !review.context_current) throw new Error("Rebuild current source context before adding memory");
      item = await api("/api/memory", { ...values, contact: $("contact").value });
    }
    await afterMemory(item);
  });
});
$("memory-withdraw").addEventListener("click", () => perform(async () => {
  if (!$("memory-reason").value.trim()) throw new Error("Provide a reason for withdrawal");
  const item = await api(`/api/memory/${memoryItem.memory_id}/withdraw`, { expected_revision: memoryItem.revision, reason: $("memory-reason").value });
  await afterMemory(item); notice("Memory withdrawn; its revision history is retained.");
}));
$("current-time").addEventListener("click", () => perform(async () => { $("cutoff").value = new Date().toISOString(); await refreshMemory(); notice("Cutoff updated. Create a new review to rebuild its context."); }));
$("cutoff").value = new Date().toISOString();
perform(async () => {
  const result = await api("/api/contacts");
  result.contacts.forEach(item => { const option = addText($("contact"), "option", item.contact); option.value = item.contact; });
  selectedContact = $("contact").value;
  await refreshContact();
  notice(result.contacts.length ? "Choose a topic or open a saved review." : "No conversations for this owner. Import messages first.");
});

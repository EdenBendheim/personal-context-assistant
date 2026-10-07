"use strict";
const $ = id => document.getElementById(id);
let review = null;
let selectedContact = "";
let busy = false;

function notice(text, error = false) {
  $("notice").textContent = text;
  $("notice").dataset.error = String(error);
}
function dirty() { return review && $("draft").value !== review.text; }
function controls() {
  document.querySelectorAll("input,select,textarea,button").forEach(el => { el.disabled = busy; });
  $("record").disabled = busy || Boolean(dirty());
  $("decision").querySelector('[value="usable"]').disabled = Boolean(review && !review.context_current);
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
    addText(section, "h3", styles ? `${item.source} · ${item.timestamp}` : `${item.key} · ${item.kind}`);
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
function discardAllowed() { return !dirty() || window.confirm("Discard unsaved draft wording?"); }
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
  if (!discardAllowed()) { $("contact").value = selectedContact; return; }
  selectedContact = $("contact").value; review = null; $("workspace").hidden = true;
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
window.addEventListener("beforeunload", event => { if (dirty()) { event.preventDefault(); event.returnValue = ""; } });
$("cutoff").value = new Date().toISOString();
perform(async () => {
  const result = await api("/api/contacts");
  result.contacts.forEach(item => { const option = addText($("contact"), "option", item.contact); option.value = item.contact; });
  selectedContact = $("contact").value;
  await refreshContact();
  notice(result.contacts.length ? "Choose a topic or open a saved review." : "No conversations for this owner. Import messages first.");
});

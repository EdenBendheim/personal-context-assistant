"use strict";
const data = JSON.parse(document.getElementById("review-data").textContent);
const packet = data.packet, ratings = data.rating_template;
const $ = id => document.getElementById(id);
let dirty = false;
function add(parent, tag, text, className) {
  const el = document.createElement(tag);
  el.textContent = text;
  if (className) el.className = className;
  parent.append(el);
  return el;
}
function complete(rating) { return ["supported", "unsupported", "uncertain"].includes(rating.support) && rating.note.trim().length > 0; }
function progress() {
  const entries = Object.values(ratings.ratings), count = entries.filter(complete).length;
  $("progress").textContent = `${count} of ${entries.length} drafts rated. ${entries.length-count} pending.`;
}
function changed() { dirty = true; progress(); $("notice").textContent = "Changes are in this tab. Download to save them."; }
function show(index) {
  document.querySelectorAll("nav button").forEach((el, i) => el.setAttribute("aria-current", String(i === index)));
  const item = packet.cases[index], workspace = $("workspace");
  workspace.replaceChildren();
  add(workspace, "h2", item.case_id);
  const columns = add(workspace, "div", "", "columns"), source = add(columns, "section", "", "source");
  add(source, "h3", "Incoming message"); add(source, "p", item.current_message, "wording");
  add(source, "h3", "Reply goal"); add(source, "p", item.intent, "wording");
  add(source, "h3", "Source history");
  if (!item.history.length) add(source, "p", "No eligible history for this case.");
  for (const row of item.history) {
    const entry = add(source, "div", "", "history");
    add(entry, "p", `${row.speaker} / ${row.timestamp} / ${row.source}:${row.id}`, "metadata");
    add(entry, "p", row.body, "wording");
  }
  const drafts = add(columns, "div");
  if (!item.candidates.length) add(drafts, "p", "No draft reached review. These attempts remain in the score.", "empty");
  for (const candidate of item.candidates) {
    const rating = ratings.ratings[candidate.id], section = add(drafts, "section", "", "candidate");
    add(section, "h3", candidate.id); add(section, "blockquote", candidate.wording, "wording");
    const supportLabel = add(section, "label", "Are all factual statements supported by the history?");
    const select = add(supportLabel, "select"); select.id = `${candidate.id}-support`;
    for (const [value, title] of [["", "Choose…"], ["supported", "Supported"], ["unsupported", "Unsupported"], ["uncertain", "Uncertain"]]) {
      const option = add(select, "option", title); option.value = value;
    }
    select.value = rating.support || "";
    select.addEventListener("change", () => { rating.support = select.value || null; changed(); });
    const checks = add(section, "fieldset"); add(checks, "legend", "Which requested actions does the draft complete?");
    for (const [id, title] of Object.entries(item.criteria)) {
      const label = add(checks, "label", "", "check"), box = document.createElement("input");
      box.type = "checkbox"; box.checked = rating.completed.includes(id); label.append(box); add(label, "span", title);
      box.addEventListener("change", () => {
        rating.completed = box.checked ? [...rating.completed, id] : rating.completed.filter(value => value !== id); changed();
      });
    }
    const noteLabel = add(section, "label", "Briefly explain your judgment (required)");
    const note = add(noteLabel, "textarea"); note.maxLength = 1000; note.value = rating.note;
    note.addEventListener("input", () => { rating.note = note.value; changed(); });
  }
}
packet.cases.forEach((item, index) => {
  const button = add($("cases"), "button", item.case_id); button.type = "button";
  button.addEventListener("click", () => show(index));
});
$("reviewer-kind").addEventListener("change", event => { ratings.reviewer_kind = event.target.value || null; changed(); });
$("prior-exposure").addEventListener("change", event => { ratings.prior_exposure = event.target.value === "" ? null : event.target.value === "true"; changed(); });
$("download").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(ratings, null, 2)+"\n"], {type:"application/json"});
  const url = URL.createObjectURL(blob), anchor = document.createElement("a");
  anchor.href = url; anchor.download = `reply-ratings-${ratings.packet_sha256.slice(0,12)}.json`;
  anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); dirty = false;
  const pending = Object.values(ratings.ratings).filter(rating => !complete(rating)).length;
  $("notice").textContent = `Downloaded ratings with ${pending} drafts pending. Scoring requires all ratings and reviewer details.`;
});
window.addEventListener("beforeunload", event => { if (dirty) { event.preventDefault(); event.returnValue = ""; } });
show(0); progress();

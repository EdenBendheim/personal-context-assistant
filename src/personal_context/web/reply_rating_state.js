"use strict";
const ReplyRatingState = (() => {
  function object(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
  function sameKeys(value, keys) {
    return object(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
  }
  function restore(packet, template, input) {
    if (!sameKeys(input, ["version", "packet_sha256", "reviewer_kind", "prior_exposure", "ratings"]) ||
        input.version !== 1 || input.packet_sha256 !== template.packet_sha256) {
      throw new Error("Choose a ratings file from this exact review form.");
    }
    if (![null, "human", "assistant"].includes(input.reviewer_kind) ||
        ![null, true, false].includes(input.prior_exposure) ||
        !sameKeys(input.ratings, Object.keys(template.ratings))) {
      throw new Error("The ratings file has invalid reviewer details or draft IDs.");
    }
    const restored = {version:1, packet_sha256:input.packet_sha256, reviewer_kind:input.reviewer_kind,
      prior_exposure:input.prior_exposure, ratings:{}};
    for (const item of packet.cases) for (const candidate of item.candidates) {
      const rating = input.ratings[candidate.id];
      if (!sameKeys(rating, ["support", "completed", "note"]) ||
          ![null, "supported", "unsupported", "uncertain"].includes(rating.support) ||
          typeof rating.note !== "string" || [...rating.note].length > 1000 ||
          !Array.isArray(rating.completed) || new Set(rating.completed).size !== rating.completed.length ||
          !rating.completed.every(id => typeof id === "string" && Object.hasOwn(item.criteria, id))) {
        throw new Error(`Invalid saved rating for ${candidate.id}. Current work was kept.`);
      }
      restored.ratings[candidate.id] = {support:rating.support, completed:[...rating.completed], note:rating.note};
    }
    return restored;
  }
  return {restore};
})();
if (typeof module === "object") module.exports = ReplyRatingState;

const {test} = require('node:test');
const assert = require('node:assert/strict');
const {restore} = require('../src/personal_context/web/reply_rating_state.js');
const packet = {cases:[{criteria:{thanks:'Thank them', question:'Ask a question'}, candidates:[{id:'reply-001'}]}]};
const template = {version:1, packet_sha256:'a'.repeat(64), reviewer_kind:null, prior_exposure:null,
  ratings:{'reply-001':{support:null,completed:[],note:''}}};
function completed() { return {...structuredClone(template), reviewer_kind:'human', prior_exposure:false,
  ratings:{'reply-001':{support:'uncertain',completed:['thanks'],note:'The question assumes a commitment.'}}}; }
test('restore partial or completed ratings without mutating or aliasing input', () => {
  assert.deepEqual(restore(packet, template, template), template);
  const input = completed(), original = structuredClone(input), result = restore(packet, template, input);
  assert.deepEqual(result, original);
  result.ratings['reply-001'].completed.push('question');
  assert.deepEqual(input, original);
  assert.equal(template.reviewer_kind, null);
});
test('wrong packet, reviewer metadata or candidate IDs cannot replace current work', () => {
  for (const change of [x=>x.packet_sha256='b'.repeat(64), x=>x.version=true,
    x=>x.reviewer_kind='anonymous', x=>x.prior_exposure='false',
    x=>delete x.ratings['reply-001'], x=>x.ratings.extra=x.ratings['reply-001'], x=>x.extra='unexpected']) {
    const input=completed(); change(input);
    assert.throws(()=>restore(packet,template,input));
  }
  assert.deepEqual(restore(packet,template,template),template);
});
test('malformed judgments, duplicate or foreign actions and oversized notes are refused', () => {
  for (const value of [null, [], {support:'yes',completed:[],note:'Note'},
    {support:'supported',completed:['thanks','thanks'],note:'Note'},
    {support:'supported',completed:['unknown'],note:'Note'},
    {support:'supported',completed:['toString'],note:'Note'},
    {support:'supported',completed:[],note:'x'.repeat(1001)}]) {
    const input=completed(); input.ratings['reply-001']=value;
    assert.throws(()=>restore(packet,template,input));
  }
});

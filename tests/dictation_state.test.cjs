// Exercise the shared real mic handler with delayed bridge responses.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../bonaventure/ui/dictation.js'), 'utf8');
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function harness() {
  const classes = new Set(), intervals = new Map();
  let timer = 0, starts = 0, stops = 0;
  const btn = { classList: { add: name => classes.add(name), remove: name => classes.delete(name) } };
  const field = { value: 'Typed context.', classList: { add() {}, remove() {} }, dispatchEvent() {} };
  const api = {
    start_dictation: async () => { starts++; return { ok: true }; },
    stop_dictation: async () => { stops++; return { text: 'Final transcript.' }; },
    dictation_partial: async () => ({ text: 'live words', recording: true })
  };
  const context = vm.createContext({ pywebview: { api },
    document: { getElementById: () => field }, Event: class {},
    setInterval: fn => { intervals.set(++timer, fn); return timer; },
    clearInterval: id => intervals.delete(id), console
  });
  vm.runInContext(source, context);
  const toggle = () => context.toggleMic(btn, 'symptoms');
  return { api, context, btn, field, intervals, classes, toggle,
    starts: () => starts, stops: () => stops,
    state: () => vm.runInContext('micState', context) };
}
(async () => {
  // A click while final transcription runs must never restart the recorder.
  let h = harness();
  await h.toggle();
  const final = deferred();
  h.api.stop_dictation = () => final.promise;
  const stopping = h.toggle();
  assert.equal(h.state(), 'stopping');
  assert(!h.classes.has('rec'));
  assert.match(h.btn.title, /Microphone off/);
  await h.toggle();
  assert.equal(h.starts(), 1);
  final.resolve({ text: 'Finished.' }); await stopping;
  assert.equal(h.state(), 'idle');
  assert.equal(h.intervals.size, 0);
  assert.equal(h.field.value, 'Typed context. Finished.');

  // A stop request during start is queued, not interpreted as another start.
  h = harness();
  const start = deferred();
  let startCalls = 0;
  h.api.start_dictation = () => { startCalls++; return start.promise; };
  const starting = h.toggle();
  await h.toggle();
  start.resolve({ ok: true }); await starting;
  assert.equal(startCalls, 1);
  assert.equal(h.stops(), 1);
  assert.equal(h.state(), 'idle');
  assert.equal(h.intervals.size, 0);

  // Old captions cannot overwrite the final result or a new recording.
  h = harness();
  await h.toggle();
  const partial = deferred();
  h.api.dictation_partial = () => partial.promise;
  const tick = [...h.intervals.values()][0];
  const pendingCaption = tick();
  await h.toggle();
  assert.equal(h.field.value, 'Typed context. Final transcript.');
  await h.toggle();
  partial.resolve({ text: 'stale words after stopping', recording: true });
  await pendingCaption;
  assert.equal(h.field.value, 'Typed context. Final transcript.');
  await h.toggle();

  // Rejected start/stop calls release the UI and allow retry.
  h = harness();
  h.api.start_dictation = async () => { throw new Error('microphone unavailable'); };
  await h.toggle();
  assert.equal(h.state(), 'idle');
  assert.equal(h.btn.title, 'microphone unavailable');
  assert(!h.classes.has('busy'));
  h.api.start_dictation = async () => ({ ok: true });
  await h.toggle();
  h.api.stop_dictation = async () => { throw new Error('decoder failed'); };
  await h.toggle();
  assert.equal(h.state(), 'idle');
  assert.equal(h.intervals.size, 0);
  assert(!h.classes.has('busy'));

  // No duplicate partial calls, even when decoding is slower than polling.
  h = harness();
  await h.toggle();
  const slow = deferred();
  let polls = 0;
  h.api.dictation_partial = () => { polls++; return slow.promise; };
  const poll = [...h.intervals.values()][0];
  const pending = poll();
  await poll();
  assert.equal(polls, 1);
  slow.resolve({ recording: false, text: '' }); await pending;
  assert.equal(h.state(), 'idle');
  assert.equal(h.stops(), 1);
  console.log('Mic regressions passed: rapid clicks, pending start/stop, stale captions, bridge errors, and recorder exit.');
})().catch(error => { console.error(error); process.exitCode = 1; });

// Test the real launcher script against a small DOM/bridge, without model loads.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../bonaventure/ui/island_macos.html'), 'utf8');
const script = html.split('<script>')[1].split('</script>')[0];
const elements = new Map(), events = {}, timers = [], frames = [], calls = [];
let shellAnimations = [];
function element(id) {
  if (!elements.has(id)) {
    const classes = new Set(), properties = {};
    elements.set(id, { id, value: '', innerHTML: '', textContent: '',
      offsetHeight: { intake: 222, proc: 110, err: 180, pill: 40 }[id] || 0,
      style: { setProperty: (key, value) => { properties[key] = value; }, properties },
      classList: {
        toggle: (key, on) => on ? classes.add(key) : classes.delete(key),
        add: (key) => classes.add(key), remove: (key) => classes.delete(key),
        contains: (key) => classes.has(key)
      }, getBoundingClientRect() { return { height: this.offsetHeight }; },
      getAnimations: () => shellAnimations, focus() {}, blur() {}
    });
  }
  return elements.get(id);
}
const views = ['pill', 'intake', 'proc', 'err'].map(element);
const layout = { managed: true, notched: true, top_inset: 38, min_width: 340,
  idle_width: 228, idle_height: 40, hit_width: 380, start_expanded: false };
const api = {
  launcher_layout: async () => layout,
  island: async (...args) => { calls.push(args); },
  engine_status: async () => ({ imaging: 'ready', reasoning: 'ready' }),
  clear_intake: async () => {},
  dismiss_launcher: async () => window.dismissIsland()
};
let reducedMotion = false;
const window = {
  pywebview: { api }, addEventListener: (type, handler) => { events[type] = handler; },
  matchMedia: () => ({ matches: reducedMotion })
};
const context = vm.createContext({ window, pywebview: window.pywebview,
  document: {
    body: element('body'), documentElement: element('root'), activeElement: element('symptoms'),
    getElementById: element, addEventListener() {},
    querySelectorAll: (query) => query === '.view' ? views : []
  },
  setTimeout: (fn, delay) => timers.push({ fn, delay }),
  requestAnimationFrame: (fn) => frames.push(fn), console
});
vm.runInContext(script, context);
const state = () => vm.runInContext('view', context);
async function settle() {
  for (let i = 0; i < 8; i++) {
    await Promise.resolve();
    for (const fn of frames.splice(0)) fn();
  }
}
function advance(delay) {
  const selected = timers.filter(t => t.delay === delay);
  for (const timer of selected) { timers.splice(timers.indexOf(timer), 1); timer.fn(); }
}
(async () => {
  await events.pywebviewready();
  assert.equal(state(), 'idle');
  await settle();
  assert.deepEqual(calls.at(-1), [380, 0, 'idle']);
  await window.revealIsland(); await settle();
  assert.equal(state(), 'intake');
  assert.deepEqual(calls.at(-1), [660, 222, 'intake']);
  assert.equal(element('islandShell').style.properties['--shell-height'], '260px');
  assert(element('intake').classList.contains('show'));
  element('symptoms').value = 'Breathless for three days';
  let finishAnimation;
  shellAnimations = [{ finished: new Promise(resolve => { finishAnimation = resolve; }) }];
  const callsBeforeClose = calls.length;
  window.dismissIsland();
  assert.equal(state(), 'idle');
  assert(!element('intake').classList.contains('show'));
  assert.equal(element('symptoms').value, 'Breathless for three days');
  advance(290); await settle();
  assert.equal(calls.length, callsBeforeClose, 'native surface must not shrink before CSS completes');
  finishAnimation(); await settle();
  assert.deepEqual(calls.at(-1), [380, 0, 'idle']);
  shellAnimations = [];
  await window.revealIsland(); await settle();
  assert.equal(element('symptoms').value, 'Breathless for three days');
  // Reopening must invalidate an unfinished collapse, including cancellation.
  let cancelAnimation;
  shellAnimations = [{ finished: new Promise((resolve, reject) => { cancelAnimation = reject; }) }];
  window.dismissIsland();
  await window.revealIsland(); await settle();
  const callsAfterReopen = calls.length;
  cancelAnimation(new Error('transition cancelled')); await settle();
  assert.equal(calls.length, callsAfterReopen);
  assert.equal(state(), 'intake');
  shellAnimations = [];
  // A delayed screen-layout response must not reopen a dismissed panel.
  const pending = window.revealIsland();
  window.dismissIsland();
  await pending; await settle();
  assert.equal(state(), 'idle');
  // Preserve an in-flight analysis view on explicit hide/reopen.
  vm.runInContext("show('proc')", context); await settle();
  window.dismissIsland();
  await window.revealIsland(); await settle();
  assert.equal(state(), 'proc');
  // Once a case resets, the next reveal must open intake, not stale progress.
  window.resetLauncher();
  await window.revealIsland(); await settle();
  assert.equal(state(), 'intake');
  reducedMotion = true;
  // Reduce Motion must not wait even if a previous animation is unfinished.
  shellAnimations = [{ finished: new Promise(() => {}) }];
  window.dismissIsland();
  assert.deepEqual(calls.at(-1), [380, 0, 'idle']);
  // Non-macOS keeps the original pill, direct resize, and toggle behavior.
  Object.assign(layout, { managed: false, notched: false, top_inset: 0, min_width: 340 });
  await vm.runInContext('refreshLayout()', context);
  calls.length = 0; timers.length = 0; frames.length = 0;
  vm.runInContext("show('pill')", context);
  assert.equal(state(), 'pill');
  assert(!element('body').classList.contains('managed'));
  assert(!element('root').classList.contains('managed'));
  assert.deepEqual(calls.at(-1), [340, 40]);
  window.toggleIsland();
  assert.equal(state(), 'intake');
  assert.deepEqual(calls.at(-1), [660, 222]);
  assert(timers.some(timer => timer.delay === 250));
  window.toggleIsland();
  assert.equal(state(), 'pill');
  assert.deepEqual(calls.at(-1), [340, 40]);
  assert.equal(frames.length, 0);
  // Double-clicking must open one picker; cancellation/errors must permit retry.
  let pickerCalls = 0, cancelPicker;
  api.pick_scan = () => {
    pickerCalls++;
    return new Promise(resolve => { cancelPicker = resolve; });
  };
  const picking = vm.runInContext("pick('scan')", context);
  await vm.runInContext("pick('scan')", context);
  assert.equal(pickerCalls, 1);
  cancelPicker(null); await picking;
  api.pick_scan = async () => { throw new Error('picker failed'); };
  await vm.runInContext("pick('scan')", context);
  assert.equal(vm.runInContext('pickerBusy', context), false);
  assert.match(element('hint').textContent, /try again/);
  api.pick_scan = async () => { pickerCalls++; return null; };
  await vm.runInContext("pick('scan')", context);
  assert.equal(pickerCalls, 2);
  console.log('Launcher bridge checks passed: shell sizing, collapse timing, draft preservation, rapid toggles, analysis view, and reduced motion.');
})().catch(error => { console.error(error); process.exitCode = 1; });

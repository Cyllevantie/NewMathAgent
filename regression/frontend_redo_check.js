// 「从所选阶段重跑」**真跑**：清空之前必须先问，输入已变更时还要把
// 「只能从 ⓪ 读题 起跑」说清楚；用户取消则一个文件都不动。
//
// 纯字符串哨兵只能证明 `confirm(` 这几个字还在，钉不住「先预检还是先清空」
// 「输入变更后还会不会去撞那个注定 409 的 /api/start」——这里把真正的
// `redoFromSelected` 抠出来，配桩 `confirm` / `fetch` / `postRedo` 跑一遍。
const fs = require('fs');
const path = require('path');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'lib', 'web', 'static', 'index.html'), 'utf8');

function extract(name) {
  const i = HTML.indexOf('function ' + name + '(');
  if (i < 0) throw new Error('找不到函数 ' + name);
  const pre = HTML.slice(Math.max(0, i - 6), i) === 'async ' ? 'async ' : '';
  let depth = 0, started = false;
  for (let j = i; j < HTML.length; j++) {
    if (HTML[j] === '{') { depth++; started = true; }
    else if (HTML[j] === '}') { depth--; if (started && depth === 0) return pre + HTML.slice(i, j + 1); }
  }
  throw new Error('大括号不配平：' + name);
}
function extractConst(re, what) {
  const m = HTML.match(re);
  if (!m) throw new Error('找不到常量 ' + what);
  return m[0];
}

const CONSTS = [
  extractConst(/const STAGE_ORDER=\[[^\n]*\];/, 'STAGE_ORDER'),
  extractConst(/const STAGE_NAME=\{[^\n]*\};/, 'STAGE_NAME'),
].join('\n');
const SRC = ['lateStartPreflight', 'redoConsequence', 'redoStageNames',
             'redoFromSelected'].map(extract).join('\n');

// ---- 桩：confirm/alert/fetch/postRedo/pauseAndWait/dvPayload/loadState ----
let confirms = [], alerts = [], confirmQueue = [];
let preReply = { ok: true, detail: '' };
let preHttp = { ok: true, status: 200 };
let preflightCalls = [], startBodies = [], redoQueue = [], redoCalls = [], pauses = 0;
const els = { stage_sel: { value: 'demo' }, dv_dir: { value: '' }, dv_template: null };

function confirm(msg) { confirms.push(msg); return confirmQueue.length ? confirmQueue.shift() : true; }
function alert(msg) { alerts.push(msg); }
function $(id) { return els[id] || null; }
async function fetchStub(url, opts) {
  if (url.indexOf('/api/start/preflight') === 0) {
    preflightCalls.push(url);
    return { ok: preHttp.ok, status: preHttp.status, json: async () => preReply };
  }
  if (url === '/api/start') {
    startBodies.push(opts && opts.body);
    return { ok: true, json: async () => ({ ok: true }) };
  }
  throw new Error('unexpected fetch ' + url);
}
async function postRedo(stage) {
  redoCalls.push(stage);
  return redoQueue.length ? redoQueue.shift() : { ok: true, cleared: ['x'] };
}
async function pauseAndWait() { pauses++; return { ok: true }; }
function dvPayload(from) { return JSON.stringify({ from_stage: from }); }
async function loadState() {}

const run = new Function(
  'confirm', 'alert', '$', 'fetch', 'postRedo', 'pauseAndWait', 'dvPayload', 'loadState',
  CONSTS + '\n' + SRC + '\nreturn {redoFromSelected};'
)(confirm, alert, $, fetchStub, postRedo, pauseAndWait, dvPayload, loadState);

function reset(opts) {
  confirms = []; alerts = []; confirmQueue = (opts.confirms || []).slice();
  preReply = opts.pre || { ok: true, detail: '' };
  preHttp = opts.preHttp || { ok: true, status: 200 };
  preflightCalls = []; startBodies = [];
  redoQueue = (opts.redos || []).slice(); redoCalls = []; pauses = 0;
  els.stage_sel.value = opts.stage || 'demo';
}

let bad = 0;
function ck(cond, msg) {
  console.log((cond ? '✓' : '✗') + ' ' + msg);
  if (!cond) bad++;
}

(async () => {
  ck(HTML.includes("$('redo_btn').onclick=redoFromSelected;"),
     '按钮真的接到带预检的处理器（不是新函数晾着、旧 handler 还在）');

  // ---- 1. 输入已变更：确认框说清「清空后只能从 ⓪ 读题 起跑」，确认后只清空、不起跑 ----
  reset({
    pre: { ok: false, detail: '输入已变更（`request/` 或 `data/` 与上一轮不同），不能从「⑯ 交互Demo」起跑。' },
    confirms: [true],
  });
  await run.redoFromSelected();
  ck(preflightCalls.length === 1 && preflightCalls[0].includes('from_stage=demo'),
     '清空前先问预检（不是清完才撞 409）');
  ck(confirms[0].includes('输入已变更') && confirms[0].includes('从 ⓪ 读题'),
     '确认框写明输入已变更 / 只能从 ⓪ 读题 起跑');
  ck(confirms[0].includes('仍要清空') && confirms[0].includes('⑯ 交互Demo'),
     '确认框问的是「仍要清空该阶段及之后产物吗」');
  ck(redoCalls.length === 1 && redoCalls[0] === 'demo', '确认后才清空');
  ck(startBodies.length === 0, '输入已变更时不再拿注定 409 的 from_stage 去起跑');
  ck(alerts.some(a => a.includes('已清空') && a.includes('点 ▶ 开始全链')),
     '清空后如实提示从 ▶ 开始全链');

  // ---- 2. 用户取消：一个文件都不动 ----
  reset({ pre: { ok: false, detail: '输入已变更' }, confirms: [false] });
  await run.redoFromSelected();
  ck(redoCalls.length === 0 && startBodies.length === 0,
     '取消确认 ⇒ 不清空、不起跑');

  // ---- 3. 输入未变：原行为不变（确认 → 清空 → 自动从该阶段起跑）----
  reset({ pre: { ok: true, detail: '' }, confirms: [true] });
  await run.redoFromSelected();
  ck(confirms[0].includes('随后从该阶段重跑'), '输入未变时确认框仍是“随后从该阶段重跑”');
  ck(redoCalls.length === 1 && redoCalls[0] === 'demo', '输入未变时清空所选阶段');
  ck(startBodies.length === 1 && JSON.parse(startBodies[0]).from_stage === 'demo',
     '输入未变时清空后自动从该阶段起跑（不是从 ⓪ 读题）');
  ck(alerts.some(a => a.includes('已从「⑯ 交互Demo」开始重跑')),
     '成功提示仍在');

  // ---- 4. 链正在跑 + 输入已变更：暂停 → 清空 → 停住，不起跑 ----
  reset({
    pre: { ok: false, detail: '输入已变更' },
    confirms: [true, true],
    redos: [{ ok: false, why: '运行中不能移动阶段产物' }, { ok: true, cleared: ['x'] }],
  });
  await run.redoFromSelected();
  ck(pauses === 1 && redoCalls.length === 2, '运行中确认后先暂停再重试清空');
  ck(startBodies.length === 0, '这条分支也不去撞 409');
  ck(alerts.some(a => a.includes('已暂停并清空')), '暂停清空后如实提示');
  ck(alerts.some(a => a.includes('从 ⓪ 读题 起跑')), '提示 ⓪ 读题 是唯一出路');

  // ---- 5. 链正在跑 + 输入未变：暂停 → 清空 → 从该阶段起跑（原行为）----
  reset({
    pre: { ok: true, detail: '' },
    confirms: [true, true],
    redos: [{ ok: false, why: '运行中不能移动阶段产物' }, { ok: true, cleared: ['x'] }],
  });
  await run.redoFromSelected();
  ck(pauses === 1 && redoCalls.length === 2, '运行中确认后先暂停再重试清空');
  ck(startBodies.length === 1 && JSON.parse(startBodies[0]).from_stage === 'demo',
     '输入未变时暂停清空后仍从该阶段起跑');
  ck(preflightCalls.length === 2, '暂停后重新核对一次输入版本');

  // ---- 6. 预检接口不可用（旧版驱动/500）：允许清空，但绝不自动起跑 ----
  reset({
    pre: { ok: true, detail: '' },
    preHttp: { ok: false, status: 404 },
    confirms: [true],
  });
  await run.redoFromSelected();
  ck(confirms[0].includes('无法核对输入版本'), '预检不可用时确认框如实说“无法核对”');
  ck(redoCalls.length === 1 && startBodies.length === 0,
     '预检不可用时清空但不自动起跑（不赌旧版 /api/start 有 409）');
  ck(alerts.some(a => a.includes('不会自动起跑')), '清空后提示不会自动起跑');

  console.log(bad ? ('\n' + bad + ' 条失败') : '\n全部通过');
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });

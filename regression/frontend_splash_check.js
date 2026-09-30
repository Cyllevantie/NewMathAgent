// 把 index.html 的整段 <script> 放到桩 DOM 里**真跑一遍**，验三件事：
//   ① 配置齐了 ⇒ 走 boot 模式，过渡动画之后**才**建 EventSource（主界面起来）
//   ② 没配好  ⇒ 停在 config 模式，**不建** EventSource、**不起**轮询
//      （否则主界面会在配置页后面偷跑：轮询照打、日志照刷，"没配好"就只是个摆设）
//   ③ `[1M]` 勾选框**保留原写法**（盘上现在是 [1M]，不许被悄悄改成 [1m]）
// 手法：setTimeout/setInterval 换成"收集回调、由测试手动触发" ⇒ "过渡之后"是可测的。
const fs = require('fs');
const path = require('path');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'lib', 'web', 'static', 'index.html'), 'utf8');
const SCRIPT = HTML.match(/<script>([\s\S]*?)<\/script>/)[1];
const tick = () => new Promise((r) => setImmediate(r));

function makeEnv() {
  const els = {}; let esCount = 0; const intervals = []; const timers = []; const fetches = [];
  const node = (id) => els[id] || (els[id] = {
    id, style: {}, dataset: {}, children: [null], innerHTML: '', textContent: '', value: '',
    className: '', placeholder: '', checked: false, disabled: false,
    _ls: {}, addEventListener(ev, fn) { (this._ls[ev] = this._ls[ev] || []).push(fn); }, focus() {},
    classList: { add() {}, remove() {}, contains: () => false },
  });
  global.document = { getElementById: (id) => (id ? node(id) : null), querySelector: () => null,
                      querySelectorAll: () => [], addEventListener() {} };
  global.window = { open() {} };
  // 浏览器里 `addEventListener(...)` 解析到的是**全局**那个（window 上的）——
  //   桩里必须补上，否则页面上任何顶层 `addEventListener` 都会 "is not defined"
  //   并把整段脚本炸掉（例如 GitHub 标识浮层的 Esc 关闭那个监听器）。
  global.addEventListener = () => {};
  global.EventSource = function () { esCount++; this.onmessage = null; };
  global.setInterval = (fn, ms) => { intervals.push([fn, ms]); return 1; };
  global.setTimeout = (fn, ms) => { timers.push([fn, ms || 0]); return timers.length; };
  global.confirm = () => false;
  global.prompt = () => null;
  global.esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  global.fetch = async (url) => {
    fetches.push(String(url));
    const u = String(url);
    if (ENV.failConfig && u.startsWith('/api/model_config') && !u.includes('/test'))
      throw new Error('boom');
    if (u.startsWith('/api/model_config/test'))
      return { ok: true, json: async () => ({ ok: true, ms: 123, reply: '可以', proxy: '🌐 策略=auto' }) };
    if (u.startsWith('/api/model_config'))
      return { ok: true, json: async () => Object.assign({ ok: true }, ENV.cfg) };
    if (u.startsWith('/api/browse'))
      return { ok: true, json: async () => ({ ok: true, path: 'C:\\repo', parent: 'C:\\',
                                              dirs: ['a', 'b'], truncated: false }) };
    return { ok: true, json: async () => ({}) };
  };
  global.__runTimers = () => {                    // 跑光所有排队的定时器（含它们新排的）
    for (let i = 0; i < 40 && timers.length; i++) timers.shift()[0]();
  };
  global.__state = () => ({ esCount, intervals, fetches, els, get: node });
  return global.__state;
}

const ENV = { cfg: {} };
let bad = 0;

async function runCase(label, cfg, expectMain, failConfig) {
  ENV.cfg = cfg; ENV.failConfig = !!failConfig;
  const state = makeEnv();
  try {
    new Function(SCRIPT)();
  } catch (e) {
    console.log('✗ [' + label + '] 脚本抛错：' + e.message); bad++; return;
  }
  await tick();                    // 让 boot() 里的 `await fetch(...)` 落地
  await tick();
  global.__runTimers();            // 再跑过渡动画的定时器
  const s = state();
  const mode = s.get('splash').dataset.mode;
  const started = s.esCount > 0;
  // 只看**4000ms 那个状态轮询**：页面上还有个 1 秒的计时器跳字，
  //   它一直都在跑，拿 '有没有 setInterval' 判会永远为真 —— 那就成了摆设。
  const polling = s.intervals.some(([, ms]) => ms === 4000);
  const ok = (started === expectMain) && (mode === (expectMain ? 'boot' : 'config')) && (polling === expectMain);
  console.log((ok ? '✓' : '✗') + ' ' + label.padEnd(12) +
    ' splash.mode=' + String(mode).padEnd(7) + ' 建SSE=' + String(started).padEnd(5) +
    ' 状态轮询=' + (polling ? '有' : '无').padEnd(3) +
    ' 模型框=' + JSON.stringify(s.get('cf_model').value).padEnd(20) +
    ' [1m]勾选=' + s.get('cf_1m').checked + ' 直接进入按钮=' + (s.get('cf_back').style.display||'none'));
  if (!ok) bad++;
  return s;
}

(async () => {
  await runCase('配好了', { configured: true, base_url: 'https://api.x.com',
    model: 'deepseek-flash[1M]', has_key: true, key_masked: 'sk-1…ab', note: '🧩 .env' }, true);
  await runCase('没配好', { configured: false, missing: ['ANTHROPIC_MODEL'], base_url: '',
    model: '', has_key: false, note: '🧩 CLI' }, false);
  await runCase('无后缀模型', { configured: true, base_url: 'https://api.x.com',
    model: 'gpt-x', has_key: true, key_masked: '（已设）', note: '' }, true);
  const s = await runCase('配置端点挂了', {configured:false}, false, true);
  // 配置页上「直接进入」常驻（按钮文案就叫这个）—— 也覆盖"读不到配置状态"那条路
  const notLocked = s && s.get('cf_back').style.display === 'inline-block';
  console.log((notLocked?'✓':'✗') + ' 配置页上"直接进入"常驻：' + (s?s.get('cf_back').style.display:'?'));
  if(!notLocked) bad++;

  // 勾选框：勾上要把后缀**当场写进模型框**（勾上后模型名后面要出现 [1m]）。
  //   这里**真的触发 change 事件**（桩节点记录了监听器）—— 顺带把"接线"也验了，
  //   比直接调函数强：函数改名/没绑上都会被抓到。
  {
    const s = makeEnv(); ENV.failConfig = false;   // 别继承上一条的「端点挂了」
    ENV.cfg = { configured:false, base_url:'https://x', model:'deepseek-flash[1M]', has_key:true };
    new Function(SCRIPT)();
    await tick(); await tick();
    const cb = s().get('cf_1m'), el = s().get('cf_model');
    // 装载态也必须是"框里有后缀 + 勾选框勾上"（刷新后 [1M] 必须显示在模型名后面）。
    //   那不只是显示问题：`modelFromForm()` 取的是**框里的值**，装载时不写回 ⇒ 一点「保存并进入」
    //   就会把 `[1M]` 悄悄丢掉。所以这条断言直接钉"装载后的框里带不带后缀"。
    const loaded = el.value, loadedChecked = cb.checked;
    cb.checked = false;
    (cb._ls.change || []).forEach(f => f());
    const off = el.value;
    cb.checked = true;
    (cb._ls.change || []).forEach(f => f());
    const on = el.value;
    const ok = loaded === 'deepseek-flash[1M]' && loadedChecked === true
            && off === 'deepseek-flash' && on === 'deepseek-flash[1M]';
    console.log((ok?'✓':'✗') + ' 勾选框与装载态：装载 ' + JSON.stringify(loaded) + '(' + loadedChecked + ')'
                + ' → 取消 ' + JSON.stringify(off) + ' → 勾 ' + JSON.stringify(on)
                + '（原值大写 [1M] 要保住）');
    if (!ok) bad++;
  }
  // boot 模式（配好了直接进）下不该显示「直接进入」—— 那时没有配置页
  {
    const s2 = makeEnv(); ENV.failConfig = false;
    ENV.cfg = { configured:true, base_url:'https://x', model:'m', has_key:true };
    new Function(SCRIPT)();
    await tick(); await tick();
    const shown = s2().get('cf_back').style.display || 'none';
    const ok2 = shown === 'none';
    console.log((ok2?'✓':'✗') + ' boot 模式下不显示「直接进入」：' + shown);
    if (!ok2) bad++;
  }
  console.log(bad ? ('★ ' + bad + ' 例不符') : '启动门控与 [1M] 回读符合预期（含不锁死）');
  process.exit(bad ? 1 : 0);
})();

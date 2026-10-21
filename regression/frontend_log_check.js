// 日志拆段纯函数哨兵：真实 tool 行（缩进 + 图标 + [sid] + Tool:/工具报错:）必须能拆开，
// 否则整行落进 .lx，五套主题的 .tk/.cmd 配色永远不生效。
const fs = require('fs');
const path = require('path');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'lib', 'web', 'static', 'index.html'), 'utf8');

function extract(name) {
  const i = HTML.indexOf('function ' + name + '(');
  if (i < 0) throw new Error('找不到函数 ' + name);
  let depth = 0, started = false;
  for (let j = i; j < HTML.length; j++) {
    if (HTML[j] === '{') { depth++; started = true; }
    else if (HTML[j] === '}') { depth--; if (started && depth === 0) return HTML.slice(i, j + 1); }
  }
  throw new Error('大括号不配平：' + name);
}

const ICON_ART = { '🧩': 'px-tgem', '🛠': 'px-tterm', '✗': 'px-warn', '✅': 'px-tcheck' };
const logParts = new Function('ICON_ART', extract('logParts') + '\nreturn logParts;')(ICON_ART);
const logTokens = new Function(extract('logTokens') + '\nreturn logTokens;')();

let bad = 0;
function ck(cond, msg) {
  console.log((cond ? '✓' : '✗') + ' ' + msg);
  if (!cond) bad++;
}

const a = logParts('[13:01:31] 🧩 模型配置来源：项目 .env');
ck(a.time === '[13:01:31]' && a.icon === 'px-tgem' && a.text.includes('模型配置来源'),
   '时间戳 + 图标 + 正文');

const b = logParts('  🛠 [literature] Tool: WebSearch');
ck(b.indent === '  ' && b.icon === 'px-tterm' && b.tag === '[literature]' && b.cmd === 'Tool:' && b.text === 'WebSearch',
   '缩进 + 图标 + [sid] + Tool:');

const c = logParts('  ✗ [demo] 工具报错: boom');
ck(c.indent === '  ' && c.icon === 'px-warn' && c.tag === '[demo]' && c.cmd === '工具报错:' && c.text === 'boom',
   '中文错误前缀 也进 .cmd');

const d = logParts('[demo] Bash: ls -la');
ck(d.tag === '[demo]' && d.cmd === 'Bash:' && d.text === 'ls -la', '[demo] Bash: 拆段');

const e = logParts('[第 17/17 步] 交互Demo 开始');
ck(!e.tag && e.text.includes('[第 17/17 步]'), '中文方括号不被当成工具标签');

// 正文语义色：路径 / 文件 / URL·IP / 时间 / 数值 / 告警 / 完成
function tok(s) {
  return logTokens(s).filter(t => t.cls).map(t => [t.text, t.cls]);
}
ck(tok('复用探针：_tmp/membrane_modes.py（上一轮同批对象）').some(x => x[1] === 'log-path'),
   '相对路径进 .log-path');
ck(tok('读取 reports/FIGURE_PLAN.md · 三张候选图').some(x => x[1] === 'log-path'),
   'reports/ 路径进 .log-path');
ck(tok('写 demo/demo.html（内联三维引擎 17.4 KB）').some(x => x[1] === 'log-path'),
   'demo/ 路径进 .log-path');
ck(tok('截图 2/3 超时，自动重试一次（第一次 12.4s）').some(x => x[1] === 'log-time' && x[0] === '12.4s'),
   '12.4s 进 .log-time');
ck(tok('交互Demo 完成（33 分 58 秒）').some(x => x[1] === 'log-time' && x[0].includes('33')),
   '33 分 58 秒 进 .log-time');
ck(tok('打包产物 → 提交作品/最新作品/demo.html').some(x => x[1] === 'log-path'),
   '中文目录路径进 .log-path');
ck(tok('写入 RECEIPT_LEDGER.json · 回执已签').some(x => x[1] === 'log-file'),
   '裸文件名进 .log-file');
ck(tok('截图 2/3 超时').some(x => x[1] === 'log-warn'), '超时进 .log-warn');
ck(tok('交互Demo 完成').some(x => x[1] === 'log-ok'), '完成进 .log-ok');
ck(!tok('任务未完成').some(x => x[1] === 'log-ok'), '未完成不进 .log-ok');
ck(!tok('未通过').some(x => x[1] === 'log-ok'), '未通过不进 .log-ok');
ck(tok('https://example.com/x').some(x => x[1] === 'log-url'), 'URL 进 .log-url');
ck(tok('web 就绪 http://127.0.0.1:8901').some(x => x[1] === 'log-url'), 'IP:port 进 .log-url');
for (const c of ['log-path','log-file','log-url','log-time','log-num','log-warn','log-ok']) {
  ck(HTML.includes('.lx .' + c), `有 .lx .${c} 样式`);
}

// 五套皮肤（dark 没有 data-theme 块，走 base）都应有四段规则。
for (const t of ['sketch', 'blueprint', 'pixel', 'editorial']) {
  for (const s of ['lt', 'tk', 'cmd', 'lx']) {
    ck(HTML.includes('html[data-theme="' + t + '"] .logpane .' + s),
       `${t} 有 .logpane .${s} 规则`);
  }
}
for (const s of ['lt', 'tk', 'cmd', 'lx']) {
  ck(HTML.includes('.logpane .' + s + '{'), `base 有 .logpane .${s} 规则`);
}

console.log(bad ? ('★ ' + bad + ' 例不通过') : '全部通过（日志拆段与五套配色规则）');
process.exit(bad ? 1 : 0);

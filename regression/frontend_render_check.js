// 把 index.html 里的 renderIntakePanel / ikToggleEdit 抠出来，用桩 DOM 真跑一遍。
// 判据：① 不抛错；② 生成的 HTML **标签配平**；③ 该有的东西都在（PDF 内嵌、渲染容器、确认表）。
// 这是没有浏览器时能拿到的最硬的证据 —— 光看 `node --check` 只能证明"语法对"。
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

// ---- 桩 ----
const nodes = {};
function mkNode(id) {
  return {
    id, style: {}, dataset: {}, children: [null], innerHTML: '', textContent: '', value: '',
    className: '', _h: {},
    addEventListener() {}, focus() {},
  };
}
const documentStub = {
  getElementById: (id) => (nodes[id] = nodes[id] || mkNode(id)),
  querySelector: () => null, querySelectorAll: () => [],
};
global.document = documentStub;
global.window = { open() {} };
global.fetch = async () => ({ json: async () => ({ ai: '# 题面\n| a | b |\n', report_path: 'reports/INTAKE_REPORT.md' }) });
global.openFile = () => {};
global.esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
global.mdToHtml = (s) => '<div>' + String(s) + '</div>';
global.IK_ROLES = [['problem', '题面'], ['attachment', '附件'], ['data', '数据'], ['ignore', '忽略'], ['needs_manual', '需人工']];
global.$ = (id) => nodes[id] || null;
let _ikLoadedFor = null;

const src = [extract('renderIntakePanel'), extract('ikToggleEdit')].join('\n');
const run = new Function('return (function(){ let _ikLoadedFor=null;' + src +
  '; return {renderIntakePanel, ikToggleEdit, getLoaded: ()=>_ikLoadedFor}; })()')();

function count(html) {
  const open = (html.match(/<div\b/g) || []).length;
  const close = (html.match(/<\/div>/g) || []).length;
  const oo = (html.match(/<object\b/g) || []).length, oc = (html.match(/<\/object>/g) || []).length;
  const to = (html.match(/<textarea\b/g) || []).length, tc = (html.match(/<\/textarea>/g) || []).length;
  const so = (html.match(/<span\b/g) || []).length, sc = (html.match(/<\/span>/g) || []).length;
  const to2 = (html.match(/<table\b/g) || []).length, tc2 = (html.match(/<\/table>/g) || []).length;
  return { open, close, oo, oc, to, tc, so, sc, to2, tc2 };
}

const rows = [
  { path: 'request/_inbox/A题/题目.pdf', role: 'problem', target: 'request/attachments/A题/题目.pdf', why: '题面' },
  { path: 'request/_inbox/A题/附件1.xlsx', role: 'data', target: 'data/附件1.xlsx', why: '数据' },
];
const base = { kind: 'intake', stage: 'intake', report_path: 'reports/INTAKE_REPORT.md',
               facts: { ai: { pages: 4, chars: 3200, subquestions: 3, files: 2 } } };

let bad = 0;
for (const [label, payload] of [
  ['有 PDF（题面那一行 role=problem）', { ...base, files: rows }],
  ['没有 PDF（题面是 .md）', { ...base, files: [{ path: 'request/_inbox/题目.md', role: 'problem', target: 'request/attachments/题目.md', why: '' }] }],
  ['空 files', { ...base, files: [] }],
  ['别的黄灯（kind != intake）', { kind: 'overtime', stage: 'code' }],
]) {
  const n = documentStub.getElementById('dc_intake');
  n.innerHTML = ''; n.style = {}; n.dataset = {}; n.children = [null];
  try {
    run.renderIntakePanel(payload);
  } catch (e) {
    console.log('✗ 抛错 [' + label + ']:', e.message); bad++; continue;
  }
  const h = n.innerHTML;
  const c = count(h);
  const ok = c.open === c.close && c.oo === c.oc && c.to === c.tc && c.so === c.sc && c.to2 === c.tc2;
  const parts = [];
  if (h.includes('id="ik_view"')) parts.push('渲染容器');
  if (h.includes('id="ik_text"')) parts.push('题面正文');
  if (h.includes('id="ik_edit"')) parts.push('改文字开关');
  if (h.includes('/api/read?path=')) parts.push('内嵌PDF');
  if (h.includes('data-ik-role')) parts.push('分类表');
  if (h.includes('id="ik_notes"')) parts.push('更正说明');
  if (h.includes('ik_mech')) parts.push('★机械栏残留');
  console.log((ok ? '✓' : '✗') + ' ' + label.padEnd(32) +
    ' div ' + c.open + '/' + c.close + '  object ' + c.oo + '/' + c.oc +
    '  含: [' + parts.join(' ') + ']');
  if (!ok) bad++;
}

// 第 5 例：**换了那份读题结果就必须重画**
//   场景：读题 A 的面板 → 面板被手动改过（脏）→ ⓪ 重跑带回读题 B（字数不同）
//   期望：面板显示 B 的题面，而不是继续显示 A 的（否则会把 A 的题面提交上去）
{
  const n = documentStub.getElementById('dc_intake');
  n.innerHTML = ''; n.style = {}; n.dataset = {}; n.children = [null];
  const A = { kind:'intake', stage:'intake', report_path:'r.md',
              facts:{ai:{chars:111,pages:1,subquestions:1,files:1}},
              files:[{path:'request/_inbox/A.pdf',role:'problem',target:'request/attachments/A.pdf',why:''}] };
  const B = { kind:'intake', stage:'intake', report_path:'r.md',
              facts:{ai:{chars:222,pages:2,subquestions:2,files:1}},
              files:[{path:'request/_inbox/B.pdf',role:'problem',target:'request/attachments/B.pdf',why:''}] };
  run.renderIntakePanel(A);
  n.dataset.dirty = '1';                       // 面板被改过（脏）
  const before = n.innerHTML;
  run.renderIntakePanel(B);                    // ⓪ 重跑带回新的一份
  const redrawn = n.innerHTML !== before && n.innerHTML.includes('B.pdf');
  console.log((redrawn ? '✓' : '✗') + ' 换了读题结果必须重画（不是继续显示旧那份）'
              + '  旧=' + (before.includes('A.pdf')) + ' 新=' + n.innerHTML.includes('B.pdf'));
  if (!redrawn) bad++;
}

console.log(bad ? ('★ ' + bad + ' 例不通过') : '全部通过（标签配平、无抛错、该有的都在）');
process.exit(bad ? 1 : 0);

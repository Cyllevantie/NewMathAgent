// 第二排正中的 GitHub 标识 + 赠言浮层。
//
// 判据（都是**会被改回去**的东西，不是阅读感想）：
//   ① 标识在 `.auxrow` 里、夹在 delivchip 与 autopilot **之间**（= 中间那一栏）；
//   ② `.auxrow` 是 `1fr auto 1fr` 三栏 grid、`#ghbadge` 居中，且**不许**退回
//      `space-between`（那个只在左右等宽时中间才真居中，而产物 chip 是变宽的）；
//   ③ 浮层三条关闭路径 + 那个链接地址一字不差；
//   ④ 字体是流光荧光（`ghflow` 关键帧 + `background-clip:text`）；
//   ⑤ 链尾自动「点」一下：认**跳变**（`_lastDone===false`），不是"当前是 true"
//      —— 后者会让每次刷新页面都再弹一遍。
const fs = require('fs');
const path = require('path');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'lib', 'web', 'static', 'index.html'), 'utf8');
const URL = 'https://github.com/Cyllevantie/NewMathAgent';

let bad = 0;
function ok(cond, label) {
  console.log((cond ? '✓ ' : '✗ ') + label);
  if (!cond) bad++;
}
const slice = (from, to) => {
  const i = HTML.indexOf(from);
  return i < 0 ? '' : HTML.slice(i, to ? HTML.indexOf(to, i) : undefined);
};

// ---- ① 位置：`.auxrow` 三件里的**中间**那件 ----
const aux = slice('class="auxrow"', '</header>');
for (const [id, label] of [['delivchip', '产物 chip'], ['ghbadge', 'GitHub 标识'], ['autopilot', '🤖托管']]) {
  ok(aux.includes('id="' + id + '"'), `第二排里有 ${label}`);
}
ok(aux.indexOf('id="delivchip"') < aux.indexOf('id="ghbadge"') &&
   aux.indexOf('id="ghbadge"') < aux.indexOf('id="autopilot"'),
   'GitHub 标识夹在「产物 chip」与「🤖托管」之间（第二排正中的那一栏）');
ok(/id="ghbadge"[\s\S]{0,4000}?<span class="gh-name">Cyllevantie<\/span>/.test(aux),
   '标识后面跟着 Cyllevantie');
ok(/id="ghbadge"[\s\S]{0,4000}?<svg/.test(aux), '标识里是 GitHub 图标（内联 SVG，不联网取图）');

// ---- ② 居中：必须是三栏 grid，且不许用 space-between ----
const rowCss = slice('.auxrow{', '}');
ok(/grid-template-columns:1fr auto 1fr/.test(rowCss), '.auxrow 是 1fr auto 1fr 三栏');
ok(!/justify-content:space-between/.test(rowCss),
   '.auxrow **不再**用 space-between（它只在左右等宽时中间才真居中）');
ok(/#ghbadge\{justify-self:center\}/.test(HTML), '#ghbadge 钉在中间那一栏');

// ---- ③ 浮层：内容、链接、三条关闭路径 ----
ok(HTML.includes('id="ghmodal"') && HTML.includes('id="ghcard"'), '有可关掉的浮层');
ok(HTML.includes('感谢使用，祝数学建模取得好成绩'), '浮层里有那句感谢');
ok(HTML.includes('跪求各位大佬点点') && /跪求[\s\S]{0,20}?star/.test(HTML), '浮层里有 star 那句');
ok(HTML.includes('href="' + URL + '"'), '浮层里有可打开的链接（' + URL + '）');
ok(/id="gh_close"/.test(HTML), '有关闭按钮 ×');
ok(/\$\('gh_close'\)\.onclick/.test(HTML), '× 挂上了关闭');
ok(/\$\('ghmodal'\)\.onclick=\(e\)=>\{[^}]*e\.target===\$\('ghmodal'\)/.test(HTML), '点浮层外也能关');
ok(/keydown[\s\S]{0,80}Escape/.test(HTML), 'Esc 也能关');

// ---- ④ 流光 + 荧光 ----
ok(/@keyframes ghflow\{/.test(HTML), '有流光关键帧 ghflow');
ok(/background-size:300% 100%[\s\S]{0,200}?animation:ghflow/.test(HTML), '渐变背景在流动');
ok(/-webkit-background-clip:text/.test(HTML), '文字用渐变裁切（流光）');
ok(/#ghbadge svg\{fill:#39ff14/.test(HTML),
   '图标给了自己的荧光色 —— 不能靠 currentColor：文字被设成 transparent 了');

// ---- ⑤ 行为：点击 + 链尾自动 ----
ok(/\$\('ghbadge'\)\.onclick=\(\)=>showGhCard\(true\)/.test(HTML), '点标识 → 弹浮层 + 开标签页');
ok(/function showGhCard\(openTab\)/.test(HTML) && /window\.open\(GH_URL/.test(HTML), 'showGhCard 会新开项目标签页');
ok(/if\(!_lastDone===false/.test(HTML) === false && /_lastDone===false&&st\.run_completed\) showGhCard\(true\)/.test(HTML),
   '链尾（run_completed 跳变）自动弹一次');
ok(/_lastDone=!!st\.run_completed/.test(HTML), '每帧记下 run_completed，供下一帧认跳变');
// 浮层里不许出现「浏览器拦掉了自动打开的标签页」那句提示 —— 钉住它不许再出现。
ok(!HTML.includes('gh_blocked') && !HTML.includes('浏览器拦掉了'),
   '浮层里**没有**那句"标签页被拦"的提示（用户要求删掉）');

console.log(bad ? `\n${bad} 项不符` : '\nGitHub 标识、赠言浮层与链尾自动弹的挂法都符合预期');
process.exit(bad ? 1 : 0);

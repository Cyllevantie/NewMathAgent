// 查看器切页签**真跑**：把 index.html 的 openFile / renderFile / markTabs 抠出来，
// 配桩 document / view / fetch 执行。
// 判据（用户 2026-10-16 报的 bug）：先开图片或 PDF（curTab='fig'/'pdf'）再点左侧报告，
// 必须切到「报告查看」并按 markdown 渲染 —— 原先的代码"保留当前页签"，会停在旧页签上。
// 纯字符串哨兵钉不住这个：一行 `if(curTab!=='md')` 写没写、条件写反没有，只有真跑才看得出来。
const fs = require('fs');
const path = require('path');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'lib', 'web', 'static', 'index.html'), 'utf8');

function extract(name) {
  const i = HTML.indexOf('function ' + name + '(');
  if (i < 0) throw new Error('找不到函数 ' + name);
  // ★ `async` 前缀要跟着带上：openFile 是 async 的，从 `function` 处切会把前缀丢掉，
  //   生成出来的代码里 `await` 就成了语法错（第一版就栽在这）。
  const pre = HTML.slice(Math.max(0, i - 6), i) === 'async ' ? 'async ' : '';
  let depth = 0, started = false;
  for (let j = i; j < HTML.length; j++) {
    if (HTML[j] === '{') { depth++; started = true; }
    else if (HTML[j] === '}') { depth--; if (started && depth === 0) return pre + HTML.slice(i, j + 1); }
  }
  throw new Error('大括号不配平：' + name);
}

let bad = 0;
function ck(cond, msg) {
  console.log((cond ? '✓' : '✗') + ' ' + msg);
  if (!cond) bad++;
}

const FUNCS = ['mdEsc', 'mdInline', 'mdToHtml', 'renderFile', 'openFile', 'markTabs'];
const src = FUNCS.map(extract).join('\n');
// 桩：openFile/renderFile 依赖的全局（curText/curFile/curTab/view/exitLogPane/fetch/document）。
// `\\n` 在生成源码里是**转义序列**（报告正文要有两行，mdToHtml 才能证明它真在解析）。
const PRELUDE = [
  "let curText=''; let curFile=null; let curTab='log';",
  "const view={className:'',innerHTML:'',textContent:'',_lp:null};",
  "function exitLogPane(){}",
  "const document={querySelectorAll:()=>[]};",
  "const fetch=async()=>({json:async()=>({text:'# 标题\\n\\n正文一段'})});",
].join('\n');

const run = new Function('return (function(){' + PRELUDE + '\n' + src + '\n'
  + 'return {openFile, renderFile, setTabRaw:(t)=>{curTab=t;}, getTab:()=>curTab,'
  + '        getFile:()=>curFile, getText:()=>curText, view}; })()')();

(async () => {
  // ---- 正路：从「图片」页签点报告 → 必须落到「报告查看」并渲染 markdown ----
  run.setTabRaw('fig');
  await run.openFile('reports/CROSS_QUESTION_REVIEW.md', false);
  ck(run.getTab() === 'md', '从图片页签点报告 ⇒ 切到报告查看（当年卡在 fig）');
  ck(run.view.className === 'markdown' && run.view.innerHTML.includes('<h2>标题</h2>'),
     '报告按 markdown 渲染（不是未解析的原文）');
  ck(run.getFile() === 'reports/CROSS_QUESTION_REVIEW.md', '当前文件跟着换成点的那份');

  // ---- 正路 2：从「PDF」页签点报告，同样必须跳 ----
  run.setTabRaw('pdf');
  await run.openFile('reports/RESULT_AUDIT_REPORT.md', false);
  ck(run.getTab() === 'md', '从 PDF 页签点报告 ⇒ 也切到报告查看');

  // ---- 对照组 1：非 md 页签时 renderFile 仍走**原文**（证明不是"renderFile 永远转 md"）----
  run.setTabRaw('fig');
  run.renderFile();
  ck(run.view.className === '' && run.view.textContent === run.getText(),
     '对照组：页签在图片时 renderFile 仍显示原文（没把渲染逻辑焊死）');

  // ---- 对照组 2：带 img=true 的图片打开路径不受影响（它提前 return，不该被拽去 md）----
  run.setTabRaw('log');
  await run.openFile('figures/fig1.png', true);
  ck(run.getTab() === 'fig' && run.view.innerHTML.includes('<img'),
     '对照组：openFile(img=true) 仍停在图片页签');

  console.log(bad ? ('★ ' + bad + ' 例不通过') : '全部通过（报告点击必跳报告查看；图片路径不受影响）');
  process.exit(bad ? 1 : 0);
})();

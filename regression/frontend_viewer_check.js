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

const FUNCS = ['esc', 'mdEsc', 'mdAttr', 'mdAssetSrc', 'mdLinkHref', 'mdMath', 'mdInline',
               'mdSplitRow', 'mdAlign', 'mdTable',
               'mdToHtml', 'figTitle', 'figCard', 'figMissing', 'renderFile', 'openFile', 'markTabs'];
const src = FUNCS.map(extract).join('\n');
// 桩：openFile/renderFile 依赖的全局（curText/curFile/curTab/curError/view/exitLogPane/fetch/document）。
// `\\n` 在生成源码里是**转义序列**（报告正文要有两行，mdToHtml 才能证明它真在解析）。
// `_resp` 可替换：404/网络失败要用不同的响应体验错误态。
const PRELUDE = [
  "let curText=''; let curFile=null; let curTab='log'; let curError='';",
  "const view={className:'',innerHTML:'',textContent:'',_lp:null};",
  "function exitLogPane(){}",
  "const document={querySelectorAll:()=>[]};",
  "const FIG_TITLES={};",
  "let figList=[]; let _figLoadToken=0;",
  "let _resp={ok:true,json:async()=>({text:'# 标题\\n\\n正文一段'})};",
  "const fetch=async()=>_resp;",
].join('\n');

const run = new Function('return (function(){' + PRELUDE + '\n' + src + '\n'
  + 'return {openFile, renderFile, setTabRaw:(t)=>{curTab=t;}, getTab:()=>curTab,'
  + '        getFile:()=>curFile, getText:()=>curText, mdInline, mdToHtml, view,'
  + '        setResp:(x)=>{_resp=x;}}; })()')();

// ---- renderSidebar 真跑：阶段徽章必须真的进 DOM，而不是"源码里还有这个词" ----
// test_frontend_files.py 里那条只是字符串哨兵：把 `${badge}` 从返回串里去掉、只留下
// `const badge=...` 的定义，哨兵照样全绿（2026-10-20 实测）。这里把真正的 renderSidebar
// 抠出来，喂一份带 stage/stage_label 的 filesList，检查**生成的 HTML**。
function extractConst(re) {
  const m = HTML.match(re);
  if (!m) throw new Error('找不到常量 ' + re);
  return m[0];
}
const SIDE_CONSTS = [
  extractConst(/const SIDE_OPEN_KEY=[^\n;]+;/),
  extractConst(/const SIDE_DEFAULT=\{[^\n]*\};/),
  extractConst(/const STAGE_NAME=\{[^\n]*\};/),
].join('\n');
const SIDE_PRELUDE = [
  "const sideEl={innerHTML:''};",
  "function $(id){ return id==='files'?sideEl:null; }",
  "const localStorage={getItem:()=>null,setItem:()=>{}};",
  "let filesList=[]; let figList=[]; let _sideFetchFailed=false;",
].join('\n');
const sideSrc = ['esc', 'sideOpenMap', 'sideIsOpen', 'renderSidebar'].map(extract).join('\n');
const sideRun = new Function('return (function(){' + SIDE_PRELUDE + '\n' + SIDE_CONSTS + '\n' + sideSrc
  + '\nreturn {renderSidebar, set:(r,f)=>{filesList=r;figList=f;}, el:sideEl}; })()')();

(async () => {
  // ---- 正路：从「图片」页签点报告 → 必须落到「报告查看」并渲染 markdown ----
  run.setTabRaw('fig');
  await run.openFile('reports/CROSS_QUESTION_REVIEW.md', false);
  ck(run.getTab() === 'md', '从图片页签点报告 ⇒ 切到报告查看（当年卡在 fig）');
  ck(run.view.className === 'markdown' && run.view.innerHTML.includes('<h1>标题</h1>'),
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

  // ---- 嵌套行内标记：链接文字里带行内码，不能漏出 T0 / 丢文字 ----
  const linked = run.mdInline('[`reports/VERIFY_REPORT.md`](reports/VERIFY_REPORT.md)');
  ck(linked.includes('<code>reports/VERIFY_REPORT.md</code>'),
     '链接文字里的行内码被渲染，而不是变成空/T0');
  ck(!linked.includes('T0') && !linked.includes('\u0000'),
     '嵌套 token 没有漏进 DOM');

  // ---- 中文硬折行：连续两行中文不能插入原文没有的空格 ----
  const joined = run.mdToHtml('第一行中文\n第二行中文');
  ck(joined.includes('第一行中文第二行中文'), '中文硬折行不插多余空格');

  // ---- 404 不得白屏：/api/read 的错误体带 detail，必须显示出来 ----
  run.setResp({ok:false,status:404,json:async()=>({detail:'不存在或不是文件'})});
  run.setTabRaw('fig');
  await run.openFile('reports/ALREADY_MOVED.md', false);
  ck(run.view.innerHTML.includes('不存在或不是文件'),
     '404 错误态显示 detail（不是空白页）');
  ck(run.view.innerHTML.trim() !== '', '404 后查看区非空（不再把 curText 清成空白）');
  run.setResp({ok:false,status:503,json:async()=>({})});
  await run.openFile('reports/RESULT_AUDIT_REPORT.md', false);
  ck(run.view.innerHTML.includes('HTTP 503'), '响应没有 detail 时显示 HTTP 状态');
  run.setResp({ok:true,json:async()=>({text:'# 标题\n\n正文一段'})});

  // ---- 安全：报告是 agent 写的，<script> 必须转义；javascript: 链接不得变成 href ----
  const scripted = run.mdToHtml('<script>alert(1)</script>');
  ck(!/<script/i.test(scripted) && scripted.includes('&lt;script&gt;'),
     '<script> 被转义（不把报告内容当代码执行）');
  const jsHref = run.mdInline('[点我](javascript:alert(1))');
  ck(!/href\s*=\s*["']?\s*javascript:/i.test(jsHref),
     'javascript: 链接不得变成 href');

  // ---- 侧栏阶段徽章真跑（见上方 SIDE_* 的说明）----
  sideRun.set([
    {name:'reports/WRITING_PLAN.md', stage:'write', stage_label:'⑨ 论文撰写'},
    {name:'reports/HIL_DECISION.md', stage_label:'人工决策'},
  ], []);
  sideRun.renderSidebar();
  const sideHtml = sideRun.el.innerHTML;
  ck(sideHtml.includes('class="filestage"') && sideHtml.includes('⑨ 论文撰写'),
     '阶段徽章真的进了侧栏 DOM（删掉 ${badge} 插值这条会变红）');
  ck(sideHtml.includes('class="file withstage"'), '报告行带 withstage 类');
  ck((sideHtml.match(/class="filestage"/g) || []).length === 2,
     '两份报告各自都带徽章（不是只渲染了第一份）');

  console.log(bad ? ('★ ' + bad + ' 例不通过') : '全部通过（报告点击必跳报告查看；图片路径不受影响；嵌套行内标记正常；错误态/转义/徽章均有真跑判据）');
  process.exit(bad ? 1 : 0);
})();

// 面板的标记顺序：脚本顶层 `$('x')` 抓的元素，id 必须出现在 `<script>` **之前**。
//
// 为什么单列一条：脚本顶层有一行 `$('gh_close').onclick=…`，若它抓的元素
// （如赠言浮层 `<div id="ghmodal">`）被放到 `</script>` **之后**，那一刻 `#gh_close`
// 还不存在 ⇒ `null.onclick` 抛 `TypeError` ⇒ **整段脚本连同 `boot()` 一起没了**：
// 阶段列表空、日志空、SSE 不建，面板看起来"什么都没了"。所以本文件的约定是
// 「标记在前、脚本在最后」—— 第 657 行 `const $=…, view=$('view')` 就靠它。
//
// 判据是纯静态的，但正好钉住那个类别：**运行时才 `$()` 的不算**（那些在事件回调里，
// 那时 DOM 早就齐了）；只查脚本**顶层**那些立刻就要用的。
//
// 「顶层」怎么认（够用且不误伤）：一行里 `$('x')` 出现在**行首或 `=` 右边**、
// 且这行不在任何 `function`/箭头函数体里。这里用一个保守近似：**行首**的
// `$('x').` / `$('x')=` 形式 —— 也就是本仓顶层赋值的那套写法。
const fs = require('fs');
const path = require('path');

// 可选 argv[2]：给别处的 html（自检/证伪时用 —— 把浮层挪到脚本后面，这条必须变红）
const HTML = fs.readFileSync(
  process.argv[2] || path.join(__dirname, '..', 'lib', 'web', 'static', 'index.html'), 'utf8');
// 先把 HTML 注释整段挖掉（换成等长空白，保住下标）再定位脚本标签：
//   注释里出现该标签的字面量会把起点定到注释里，那样定位到的不是真正的脚本标签。
const bare = HTML.replace(/<!--[\s\S]*?-->/g, m => ' '.repeat(m.length));
const scriptAt = bare.indexOf('<script');
if (scriptAt < 0) { console.log('✗ 找不到脚本标签'); process.exit(1); }
const markup = bare.slice(0, scriptAt);
const script = bare.slice(scriptAt);

let bad = 0;
function ok(cond, label) {
  console.log((cond ? '✓ ' : '✗ ') + label);
  if (!cond) bad++;
}

// ① 脚本之后不该再有任何标记 —— 一旦有，脚本顶层的 $() 就可能抓到 null
const after = HTML.slice(HTML.lastIndexOf('</script>') + '</script>'.length);
const afterTags = (after.match(/<(?!\/?(html|body)\b)[a-zA-Z][^>]*>/g) || []);
ok(afterTags.length === 0,
   `</script> 之后没有多余标记${afterTags.length ? '（实测有：' + afterTags.slice(0, 3).join(' ') + '）' : ''}`);

// ② 脚本顶层立刻取用的 id，必须已经在前面的标记里
const topLevel = [...script.matchAll(/^\$\('([^']+)'\)\s*[.=]/gm)].map(m => m[1]);
ok(topLevel.length > 0, `脚本顶层有 ${topLevel.length} 处 $('x')… 立刻取用（抽到了才说明判据不是空转）`);
const missing = [...new Set(topLevel)].filter(id => !markup.includes(`id="${id}"`));
ok(missing.length === 0,
   `这些顶层取用的 id 都在 <script> 之前定义${missing.length ? '（缺：' + missing.join('、') + ' —— 会抛 TypeError 把整段脚本带走）' : ''}`);

// ③ 对照组：这类错误最容易落在的那几处标识必须在脚本之前（钉住它们的位置本身）
for (const id of ['ghbadge', 'ghmodal', 'gh_close']) {
  ok(markup.includes(`id="${id}"`), `#${id} 在 <script> 之前`);
}

console.log(bad ? `\n${bad} 项不符` : '\n标记与脚本的先后顺序符合约定');
process.exit(bad ? 1 : 0);

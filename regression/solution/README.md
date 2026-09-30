# 解题代码的回归测试（**不属于框架套件**）

这里放的是**针对某一题解答代码**的回归测试，不是针对框架本身的。所以它**刻意**不在
`regression/` 的自动发现范围内 —— 本目录没有 `__init__.py`，而 `unittest discover`
只递归进可导入的包目录。

## 为什么不放进套件

框架套件（`python -m unittest discover -s regression`）必须能在**干净检出**上全绿。
而这里的测试：

- 需要项目根有那一轮跑出来的 `code/`（`core.py`、`robustness_2d.py`、`code/outputs/*.json`），
  而这些产物会被清进 `cache/`（驱动在题面变更时自己也会搬）；
- 断言是**那一题专属**的 —— 比如 `delta_t_dry_s == -14.58984375`、
  标签 `graded_z120_coarse` —— 换一题之后它们会**静默测着无关的东西**。

两条合起来意味着：放在套件里，它要么把干净检出拖成 ERROR，要么在换题后假绿。两种都是坏的。

## 怎么跑

```bash
# 把那一轮的 code/ 放回项目根（例如从 cache/<时间戳>_code/ 取回）
cp -r cache/20260918_185507_114507_648335_code code
python regression/solution/test_numerical_handoff.py
```

`unittest.main()` 已接在文件末尾，直接跑即可；产物不在时会**明确跳过并说明原因**，
不会抛一堆 traceback。

### 跳过条件是「导不进来」而不是真身份校验

判据是「`import core` / `import robustness_2d` 成不成功」。这在**模块名不同**时够用
（例如 `cache/074533_code` 是上一题的 code、没有 `robustness_2d.py`，会被正确跳过），
但**两题都恰好有同名模块**时它会照跑 —— 那时断言的就是另一题的数值了。

要真正钉死身份，得往 `code/` 里放一个题目标识（如 `code/PROBLEM_ID`）再比对。
暂不这么做，是因为 `code/` 是每轮生成的、加标识属于改驱动的产物契约；
真需要时再补。

## 新增同类测试时

按同样的口径判断：**断言里出现某一题的具体数值/标签/函数名 ⇒ 放这里，不放上一级。**
框架级的契约（编排、路由、门禁、篇幅、结果契约、图证据）才进 `regression/`。

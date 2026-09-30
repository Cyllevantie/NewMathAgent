# Web 驱动离线回归

在项目根目录使用已安装 FastAPI、uvicorn、python-multipart、httpx 的 Python：

```text
python -m unittest discover -s regression -v
```

测试加载真实 Web 驱动并替换启动路径和模型调用；不启动模型、不运行赛题代码、不修改已有 cache 或产物目录。临时目录由测试独占管理。

> **本目录只放框架级测试** —— 干净检出（项目根没有 `code/`、`paper/` 等跑动产物）上也必须全绿。
> 针对**某一题解答代码**的测试放在 [`solution/`](solution/README.md)：那里没有 `__init__.py`，
> 所以 `discover` 不会递归进去。判断口径见那份 README。

包含正常完成/续跑、**失败与超时转黄灯等人工决策**、裁决冲突、源版本变化、停止与异常、HTTP 状态、实际文件归档和打包行为。这些用例覆盖驱动在干净检出上必须成立的行为，必须全部通过。

# -*- coding: utf-8 -*-
"""人工定点修复后，从命令行重新认证某阶段的产物（attest）。

为什么需要它：回执答的是「盘面跟上次成功时一样吗」。人工修好的产物，答案必然是
「不一样」—— 于是驱动认为该阶段需要重做，而重做恰恰要推翻刚做好的人工修正。
`attest` 就是那个「以当前盘面重新认证」的动作。

用法（驱动需在跑，默认 127.0.0.1:8901）：

    python lib/web/attest.py                        # 只查看当前该认证哪个阶段
    python lib/web/attest.py --stage write --note "手工修好图注与表 10 的行重叠"
    python lib/web/attest.py --dry-run              # 打印将发送的请求，不提交

它做的事和不做的事：
  · 会：先让驱动跑客观校验（页数/结果契约/图证据），过不了就**拒绝认证**；
        通过后用驱动自己的回执存储写回执并自检；留下 runtime/quality/manual/ 审计痕。
  · 不会：认证门禁阶段（要放行门禁请用「接受并披露」——把 verdict 洗成 PASS
        会污染回执）；也不会对产物不存在的阶段认证（那等于往回执里撒谎）。
"""
import argparse, json, sys, urllib.error, urllib.request

DEFAULT_PORT = 8901


def call(port, payload, dry_run=False):
    url = f"http://127.0.0.1:{port}/api/decision"
    if dry_run:
        print(f"[dry-run] POST {url}\n{json.dumps(payload, ensure_ascii=False, indent=2)}")
        return 0
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return 0
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        print(f"被拒（HTTP {exc.code}）：{detail}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"连不上驱动（{url}）：{exc}\n先确认 `python lib/web/server.py` 在跑。", file=sys.stderr)
        return 2


def show_pending(port):
    url = f"http://127.0.0.1:{port}/api/state"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            st = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"连不上驱动（{url}）：{exc}", file=sys.stderr)
        return 2
    p = st.get("pending")
    if not p:
        print("当前没有待决策项。")
        return 0
    print(f"阶段 {p['stage']} · 类型 {p.get('kind')} · 状态 {p.get('status')}"
          f" · 裁决 {p.get('verdict') or '—'}")
    print(f"原因：{p.get('reason')}")
    print(f"可用动作：{p.get('actions')}")
    print(f"建议认证目标：{p.get('attest_default') or '（无）'}")
    print("\n候选阶段（✎ = 产物已被改动，回退过去会真正重跑）：")
    for c in p.get("candidates") or []:
        print(f"  {'✎' if c.get('out_changed') else ' '} {c['id']:12s}"
              f"{'（门禁，不可认证）' if not c.get('attestable') else ''}"
              f"{'（未变，回退会直接跳过）' if c.get('unchanged') else ''}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="人工修复后的重新认证 / 查看待决策项")
    ap.add_argument("--stage", help="要认证的阶段 id（默认由驱动按「产物被改过」推断）")
    ap.add_argument("--note", default="", help="说明改了什么（会写进审计痕）")
    ap.add_argument("--action", default="attest",
                    choices=["attest", "retry", "rollback", "disclose"],
                    help="默认 attest；其余动作同界面按钮")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.action == "attest" and not args.stage:
        rc = show_pending(args.port)
        print("\n上面列出了候选。确认后用 --stage <id> 提交认证。")
        return rc
    return call(args.port, {"action": args.action, "stage": args.stage, "note": args.note},
                args.dry_run)


if __name__ == "__main__":
    sys.exit(main())

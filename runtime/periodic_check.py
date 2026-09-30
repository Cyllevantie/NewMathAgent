"""NewMathAgent Web 驱动 · 只读巡检脚本（单次快照）。

用法：
    python runtime/periodic_check.py            # 打印一次完整快照（阶段/控制台/串题残留/产物时间戳）
    python runtime/periodic_check.py --line     # 只打一行紧凑快照（供每分钟 cron/loop tick 用）

用途：手动查一下"现在跑到哪、在干嘛"，或作为定时巡检的被调方。
输出读取服务器 /api/state（127.0.0.1:8901，端口可 --port 改），不改任何东西。

「串题残留」检查：把整段流水线日志（所有阶段 agent 的工具/思考/报告文本）按词表粗扫，
看是否泄漏了【上一个/其它赛题】的领域词 —— 换题回归纪律的 cheap 哨兵。
注意：
  * 词表只在换题后需要更新：把"刚跑完的上一题"的领域词 append 进 LEAK_WORDS；
    本脚本命中旧题词 = 该 stage agent 串题了（应报有，人工看是哪条 log）。
  * 是启发式关键词命中，不是语义判断；真串题可能绕开词表，仅作第一道快筛。
"""
import argparse, json, time, datetime, os, urllib.request

DEFAULT_LEAK_WORDS = [
    # 历史旧题领域词（换题时更新：把"上一批已跑完的题"的领域词放进来；当前题自己的词绝不在此列）
    "孕妇", "染色体", "BMI", "删失",      # NIPT / 产检 (2025 C)
    # 红外干涉测厚 (2025 B)。注：跨题常见词不要放（如"红外"在 B 测厚与 A 红外制导都出现，放进来会误报）
    "干涉", "外延", "测厚", "Airy", "reststrahlen", "SiC", "反射率谱",
    # 农作物种植策略 (2024 C)。注：不放"地块/亩/种植"等可能跨题出现的词
    "豆类", "小麦", "玉米", "水稻", "蔬菜", "轮作", "水浇地", "旱地", "榆黄菇", "羊肚菌",
    # 烟幕干扰弹 (2025 A)。只放强领域词；"投放/遮蔽/干扰"等
    # 泛词不入列，避免跨题误报。
    "烟幕", "干扰弹", "导弹", "无人机", "起爆", "引信", "遮蔽弹",
    # 当前题 = 2026 A 药材烘干（药材/烘干/干燥/水分浓度/烘房 是本题主场词，勿放进来，否则每次必误报）
]

def fetch(port):
    url = f"http://127.0.0.1:{port}/api/state"
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.load(r)

def snapshot(port=8901, line_only=False):
    try:
        d = fetch(port)
    except Exception as e:
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ERR 服务器不可达: {e}")
        return
    now = datetime.datetime.now().strftime("%H:%M:%S")
    cur = d.get("cur"); run = d.get("running"); el = d.get("elapsed_total")
    st = {k: v for k, v in d["stages"].items() if v not in ("idle",)}
    log = d.get("log") or []
    logtxt = "\n".join(log)
    hits = [w for w in DEFAULT_LEAK_WORDS if w in logtxt]
    last = log[-2:] if log else []
    if line_only:
        act = (last[-1][:90] if last else "")
        resid = ("有:" + ",".join(hits)) if hits else "无"
        print(f"[{now}] cur={cur} running={run} elapsed_s={el} | {act} | 串题残留:{resid}")
        return
    print(f"time: {now}   running: {run} | cur: {cur} | elapsed_s: {el}")
    print("stages:", st)
    print("log最近2:")
    for l in last:
        print("  ", l[:200])
    print("串题残留词:", hits if hits else "无")
    # 关键产物时间戳（存在才列）
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根 = new math agent
    for rel in ("paper/main.pdf", "reports/FORMAT_REPORT.md", "MATH_PROOF_REPORT.md",
                "reports/VERIFY_REPORT.md", "reports/DEMO_REPORT.md"):
        p = os.path.join(root, *rel.split("/"))
        if os.path.exists(p):
            mt = datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%m-%d %H:%M")
            print(f"  产物 {rel}: {os.path.getsize(p)}B  {mt}")
        else:
            print(f"  产物 {rel}: (未出)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8901)
    ap.add_argument("--line", action="store_true", help="只打一行紧凑快照（供定时巡检用）")
    a = ap.parse_args()
    snapshot(a.port, line_only=a.line)

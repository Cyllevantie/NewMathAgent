"""NewMathAgent Web 驱动 · 每分钟健康巡检（定时被调方）。

用法:  PYTHONIOENCODING=utf-8 python runtime/health_check.py
输出一屏快照：时间 / 运行状态 / 阶段 / 控制台活动与静默时长 / 卡住提示 / 网络或 API 报错 / 产物(报告+xlsx)。
"""
import json, time, os, socket, datetime, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOG = os.path.join(HERE, "web_run.log")
URL = "http://127.0.0.1:8901/api/state"
PROXY = "127.0.0.1:7897"      # 本机 Clash 代理（DeepSeek 长流走它）
API_HOST = "api.deepseek.com"

NET_KW = ["timeout", "timed out", "timed_out", "Connection", "connection", "refused",
          "Errno", "reset", "429", "401", "402", "403", "404", "500", "502", "503",
          "insufficient", "余额", "超时", "Clash", "proxy", "网络", "代理掐"]
WATCH_KW = ["假死", "重试", "看门狗", "taskkill", "强杀", "stalled"]

def now(): return datetime.datetime.now().strftime("%H:%M:%S")

def state():
    try:
        with urllib.request.urlopen(URL, timeout=6) as r: return json.load(r)
    except Exception as e:
        return {"err": str(e)}

def _net_probe():
    """主动网络探测（静默）：正常返回 ""。
    优先看 DeepSeek 直连（已设 NO_PROXY，主链不依赖 Clash）：直连通即正常，不报 Clash 告警；
    仅当直连也不通时才进一步报"代理也不通/经代理仍不通"。全程限时，绝不拖住巡检。"""
    direct_ok = False
    try:
        socket.create_connection((API_HOST, 443), timeout=4).close()
        direct_ok = True
    except Exception:
        direct_ok = False
    if direct_ok:
        return ""                            # DeepSeek 直连通 → 无需 Clash，正常
    try:
        h, p = PROXY.split(":")
        socket.create_connection((h, int(p)), timeout=2).close()
    except Exception:
        return "⚠️网络: DeepSeek 直连不通，且 Clash " + PROXY + " 也不通"
    try:
        ph = urllib.request.ProxyHandler({"https": f"http://{PROXY}", "http": f"http://{PROXY}"})
        op = urllib.request.build_opener(ph)
        with op.open(f"https://{API_HOST}", timeout=4):
            return ""                        # 经代理可达
    except urllib.error.HTTPError:
        return ""                            # 有 HTTP 响应=可达
    except Exception:
        return "⚠️网络: DeepSeek 直连不通，经代理也不通"
    return ""

def tail_lines(n=260):
    """优先用 /api/state 里的**内存日志**，文件只作兜底。

    为什么不能读文件：服务器启动时用 `> runtime/web_run.log` 把它的 stdout 重定向到了同一个路径，
    而 driver 的 log() 也往这个路径追加——**两个写入者各有自己的文件偏移**，uvicorn 每 4 秒写一行
    访问日志、不断推进偏移，会把 driver 写进去的行**覆盖掉**。该文件里因此只剩访问日志、
    没有 driver 输出，用它判"最近活动/静默"会得出假结论（如误报"静默 22 分钟"）。
    server 内存里的 `log` 是 deque(maxlen=4000)，内容完整，才是可信来源。
    """
    lg = state().get("log")
    if isinstance(lg, list) and lg:
        return lg
    try:
        with open(LOG, encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []


def silent_seconds(lines):
    """按**最后一条日志行自带的时间戳**算静默秒数（而不是文件 mtime——mtime 被轮询的访问日志污染）。"""
    import re
    for ln in reversed(lines or []):
        m = re.match(r"\[(\d{2}):(\d{2}):(\d{2})\]", ln.strip())
        if m:
            n = datetime.datetime.now()
            t = n.replace(hour=int(m.group(1)), minute=int(m.group(2)),
                          second=int(m.group(3)), microsecond=0)
            age = (n - t).total_seconds()
            return age if age >= 0 else age + 86400
    return None

def main():
    d = state()
    lines = tail_lines()
    print("=" * 66)
    print(f"[{now()}] FMA 健康巡检")
    if "err" in d:
        print("!! 服务器不可达:", d["err"])
        print("=" * 66)
        return
    run, cur = d.get("running"), d.get("cur")
    print(f"运行: running={run} cur={cur} | 总耗时s={d.get('elapsed_total')}")
    _np = _net_probe()
    if _np:
        print(_np)                          # 网络正常则不打，异常才提醒
    st = {k: v for k, v in d["stages"].items() if v not in ("idle",)}
    print("阶段:", st)
    # 控制台最近活动 + 静默时长
    last_tool = None
    for ln in reversed(lines):
        if "🛠" in ln or "✗" in ln or ln.strip().endswith("artifact_ok=True") or "门禁" in ln or "启动阶段" in ln:
            last_tool = ln; break
    age_s = silent_seconds(lines)
    if last_tool:
        print("最近活动:", last_tool.strip()[:150])
    # 只看日志行会**系统性误报**：驱动从不记录 `Bash` 调用（`grep -c Bash web_run.log` = 0），
    # 而"跑 solver / 导出 xlsx / 画图"这些**真干活**的步骤全是 Bash——于是计算阶段在日志里
    # 一片空白，被当成"静默/假死"。
    # 故补一路**与日志无关**的活性信号：产物文件的最后修改时刻。
    art = _artifact_activity()
    if art:
        fn, t = art
        print(f"产物活动: {fn} @{datetime.datetime.fromtimestamp(t).strftime('%H:%M:%S')}"
              f"（{int(time.time() - t)}s 前）")
    eff = age_s if age_s is not None else None
    if art:
        eff = min(eff, time.time() - art[1]) if eff is not None else (time.time() - art[1])
    if age_s is not None:
        warn = eff is not None and eff > 300 and run
        print(f"日志静默: {int(age_s)}s",
              "⚠️静默可能长生成或假死" if warn else ("（产物仍新，判为在干活）" if age_s > 300 and run else ""))
    # 错误扫描（最近 200 行内）
    recent = lines[-200:]
    net_hits = [(ln[:150]) for ln in recent if any(k.lower() in ln.lower() for k in NET_KW)]
    err_hits = [(ln[:150]) for ln in recent if "✗" in ln or "工具报错" in ln]
    watch_hits = [(ln[:150]) for ln in recent if any(k in ln for k in WATCH_KW)]
    if watch_hits: print("看门狗/重试(最近):", watch_hits[-2:])
    if net_hits:   print("⚠️ 疑似网络/API 报错(最近):", net_hits[-3:])
    elif run and age_s is not None and age_s < 200 and not err_hits:
        pass
    if err_hits:   print(f"agent 工具报错(最近200行内 {len(err_hits)} 条):", err_hits[-2:])
    # 卡住启发：以"静默+无网络错+无重试"为辅；真正卡死由服务器看门狗处理并会留下重试日志。
    if run and eff is not None and eff > 600:   # 同样以"日志静默与产物活动"的较小者为准
        print("⚠️ 已静默 >10 分钟，服务器看门狗应在 ~5 分钟超时后自动强杀重试；若重试日志未见，请人工看 UI。")
    # 产物
    reps = []
    rdir = os.path.join(ROOT, "reports")
    if os.path.isdir(rdir):
        for fn in sorted(os.listdir(rdir)):
            p = os.path.join(rdir, fn)
            if fn.endswith((".md",)) and fn[0] != "_" or fn.endswith(".md"):
                reps.append((fn, datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%m-%d %H:%M")))
    reps.sort(key=lambda x: x[1], reverse=True)
    print("最新报告:", reps[:4] if reps else "(尚无)")
    xlsx = []
    # 也要扫 results/ —— 交付的 result1-4.xlsx 实际写在这里，不扫会误报"未出"
    for base in (ROOT, os.path.join(ROOT, "data"), os.path.join(ROOT, "code"),
                 os.path.join(ROOT, "results")):
        for fn in os.listdir(base) if os.path.isdir(base) else []:
            if fn.lower().endswith(".xlsx") and "~$" not in fn:
                p = os.path.join(base, fn)
                xlsx.append((os.path.relpath(p, ROOT), datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%m-%d %H:%M")))
    print("result*.xlsx:", xlsx if xlsx else "(未出)")
    for ln in _progress_lines():
        print(ln)
    print(_input_line())
    print("=" * 66)


def _artifact_activity(dirs=("results", "figures", "code"), max_files=400):
    """最近被写过的产物文件（与日志无关的活性信号）。

    为什么要它：驱动的日志**只记录 Read/Write/Edit 与报错**，不记录 `Bash`，
    而求解、导出、绘图全是 Bash。只看日志会在计算阶段误判"静默/假死"。
    产物 mtime 不受这个盲区影响，是更可靠的活性证据。
    """
    newest = None
    n = 0
    for d in dirs:
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            continue
        for dirpath, _, files in os.walk(base):
            for fn in files:
                p = os.path.join(dirpath, fn)
                try:
                    t = os.path.getmtime(p)
                except OSError:
                    continue
                n += 1
                if newest is None or t > newest[1]:
                    newest = (os.path.relpath(p, ROOT).replace("\\", "/"), t)
                if n > max_files:
                    return newest
    rep = os.path.join(ROOT, "reports")
    if os.path.isdir(rep):
        for fn in os.listdir(rep):
            if fn.endswith(".md"):
                p = os.path.join(rep, fn)
                try:
                    t = os.path.getmtime(p)
                except OSError:
                    continue
                if newest is None or t > newest[1]:
                    newest = ("reports/" + fn, t)
    return newest


def _progress_lines():
    """产物"是否在变好"的客观信号（全部读文件，不采信任何自述）。

    ① **门禁判词趋势**：最新一份 `*.verdict.json` 的 hard 条数，与上一份对比。
       `hard 数在降 = 在收敛`——这比"报告多长"可信得多：报告变长不等于变好，
       返修甚至常让它变短（删掉不可兑现的判据句）。所以只报条数，不报篇幅当质量。
    ② **被改报告体量与增量**：回答"还在不在改"。停笔了却没出判词，才是要警惕的状态。
    历史存 `runtime/.watch_progress.json`（只存签名，不存正文）。
    """
    import glob
    rdir = os.path.join(ROOT, "reports")
    state_p = os.path.join(HERE, ".watch_progress.json")
    try:
        with open(state_p, encoding="utf-8") as f:
            hist = json.load(f)
    except Exception:
        hist = {}
    vhist, sizes = hist.get("vhist", []), hist.get("sizes", {})
    vhist = [v for v in vhist if isinstance(v, dict)]   # 丢弃旧格式（纯字符串签名）
    out = []

    # ① 判词趋势。历史也要扫 runtime/quality/feedback/**/gate_decision.json——
    # 驱动每轮回退都会把那一轮的裁决留档在那里，而 reports/ 下的侧车在回退时会被暂存走，
    # 只扫 reports/ 会在 review 正在跑的那段时间里一条都读不到（趋势线断掉）。
    # 口径以**驱动的 gate_decision.json 为准**：评审在侧车里自报的 severity 会被门禁规则改写
    # （模型层的 issue 一律升为 hard——同一轮里侧车可能写 hard=3、驱动写 hard=6）。两个数都对，
    # 但**只有驱动那个决定"必须改几条"**，混着用会让趋势线自相矛盾（同一轮出现 3 和 6 两条）。
    # 故：有 gate_decision 就只用 gate_decision；一条都没有（review 刚写完判词、驱动尚未回退）时
    # 才退回读侧车。
    vds = []
    cand = glob.glob(os.path.join(HERE, "quality", "feedback", "*", "*", "gate_decision.json"))
    if not cand:
        cand = glob.glob(os.path.join(rdir, "*.verdict.json"))
    for p in cand:
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            t = os.path.getmtime(p)
        except Exception:
            continue
        issues = d.get("issues") or []
        vds.append({
            "file": os.path.basename(p), "stage": d.get("stage"), "status": d.get("status"),
            "target": d.get("target"), "n": len(issues),
            "hard": sum(1 for i in issues if str(i.get("severity")) == "hard"),
            "at": datetime.datetime.fromtimestamp(t).strftime("%m-%d %H:%M"),
            "mtime": t,
            "sig": f"{os.path.basename(p)}|{d.get('status')}|{len(issues)}|{int(t)}",
        })
    if vds:
        cur = max(vds, key=lambda v: v["mtime"])
        # 历史存整条记录（不只是签名）：单看"上一次"会骗人——驱动在 halt 那轮**不写**
        # feedback 存档（`_halt` 在 `_save_feedback` 之前 break），序列里就可能缺一格，
        # 于是某一轮在历史里根本不存在，箭头会拿隔代的值来比（把下降显示成上升）。
        # 所以改为把**本机记录到的序列**整体印出来，缺口一眼可见，不做"上一次一定紧邻"的假设。
        if not vhist or vhist[-1].get("sig") != cur["sig"]:
            vhist.append({"sig": cur["sig"], "stage": cur["stage"], "hard": cur["hard"],
                          "n": cur["n"], "at": cur["at"]})
            vhist = vhist[-8:]
        seq = " → ".join(f"{v.get('hard')}@{v.get('at', '?')[-5:]}" for v in vhist if isinstance(v, dict))
        trend = f" ｜ 本机记录到的序列: {seq}" if seq else ""
        out.append(f"门禁判词: {cur['stage']} {cur['status']} hard={cur['hard']} 共{cur['n']}条"
                   f" → {cur['target']} @{cur['at']}{trend}")

    # ② 被改报告体量 + 增量
    newest = None
    for fn in os.listdir(rdir) if os.path.isdir(rdir) else []:
        if not fn.endswith(".md") or fn.startswith("_"):
            continue
        p = os.path.join(rdir, fn)
        try:
            t = os.path.getmtime(p)
        except OSError:
            continue
        if newest is None or t > newest[1]:
            newest = (fn, t, os.path.getsize(p))
    if newest:
        fn, t, size = newest
        prev_size = sizes.get(fn)
        sizes[fn] = size
        delta = "" if prev_size is None else f"，较上格 {size - prev_size:+d} B"
        cmt = "（仍在改）" if prev_size is not None and size != prev_size else ""
        out.append(f"最新产物: {fn} {size/1024:.1f} KB @{datetime.datetime.fromtimestamp(t).strftime('%H:%M')}"
                   f"{delta}{cmt}")

    try:
        with open(state_p, "w", encoding="utf-8") as f:
            json.dump({"vhist": vhist, "sizes": sizes}, f)
    except OSError:
        pass
    return out


def _input_line():
    """输入是否被动过：request/ + data/ 的内容指纹与开跑基线比对。

    为什么要单独盯：驱动会在每个阶段执行前后比对输入指纹，一旦不一致就判
    "执行期间输入变更" 或 "未拿到当前版本的有效裁决" → `unverified` → **转黄灯挂起**
    （面板给 `retry` / `rollback` 两个动作，但**不会自动放行**）。
    最常见的触发是往 request/ 或 data/ 加了个文件（或改错重存）。
    首次运行记基线；之后变了就报警并刷新基线。
    """
    import hashlib
    h = hashlib.sha256()
    n = 0
    for sub in ("request", "data"):
        base = os.path.join(ROOT, sub)
        if not os.path.isdir(base):
            continue
        for dirpath, _, files in os.walk(base):
            for fn in sorted(files):
                p = os.path.join(dirpath, fn)
                n += 1
                h.update(os.path.relpath(p, ROOT).replace("\\", "/").encode())
                try:
                    with open(p, "rb") as f:
                        h.update(f.read())
                except OSError:
                    pass
    digest = h.hexdigest()
    base_file = os.path.join(ROOT, "runtime", ".watch_input.json")
    try:
        with open(base_file, encoding="utf-8") as f:
            prev = json.load(f).get("digest")
    except Exception:
        prev = None
    if prev is None:
        note = "基线已记录"
    elif prev != digest:
        note = "⚠️⚠️ 输入变更！会判 unverified 转黄灯（可重试但不会自动放行）—— 立刻停止往 request//data/ 加文件"
    else:
        note = "未变"
    if prev != digest:
        try:
            with open(base_file, "w", encoding="utf-8") as f:
                json.dump({"digest": digest, "files": n, "at": now()}, f)
        except OSError:
            pass
    return f"输入(request/+data/): {n} 文件 / {note}"

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""量编译后 PDF 的行距刚性与页边距 —— 「间距一定一样」这条硬规则的机器判据。

本脚本守护的硬要求：
    正文所有东西的间距，距离上下行，大小都一样，标题自己进行统一
    （一定是这样，包括如果后续改，也遵守这个规则）

这句话由 _base/preamble.tex 机械保证，本脚本负责**验证它真的生效了**。
纯文本扫描和编译器都看不出版式问题，只有量几何量才看得出。

用法：
    python skills/14Layout-and-format/scripts/measure_layout.py <pdf> [--json out.json]

判据（任一不过 = FAIL）：
  1. **规范行距 19.9pt 的占比 ≥ 15%**（12pt × 1.2 × 1.375 = 19.8pt，取整 19.9pt）。
     用占比而不是「众数」：公式密集的文档里超高行会成为众数，而正文行距完全正常。
     样本对数 < 20 时**不判定**并如实写「样本不足」（宁可不测，也不误判）。
  2. **页边距**等于模板实际值（不是标称 2.5cm）：左 25.0 / 右 21.8 / 上 24.2 / 下 13.5 mm。

已验证的判别力（每条都做过破坏性对照）：
  ✅ 把 \\linespread{1.375} 改成 1.700 → 占比 76.2% → 0.2%，FAIL（32 页真实论文，509 样本）
  ✅ 页边距改动 → FAIL
  ✅ 带页眉的模板族 → 页眉不计入包围盒，**不**误判
  ✅ 代码附录的 listings 行号伸进左边距 → 左边界取众数，**不**误判
  ✅ 样本不足 → 报「没测」，**不**误判

**刻意没做的一条判据（记录在此，免得后人重蹈）：**
  「不得出现被挤紧的行」（行距 < 主值）听起来是 `\\lineskiplimit=-20pt` + `\\lineskip=0pt`
  的天然判据，但它**分辨不出真假**：用 `\\typeout` 确认破坏前后参数确实不同
  （`LSKIPLIM=-20 LSKIP=0` 变成 `LSKIPLIM=0 LSKIP=1`，两份 PDF 哈希也不同），
  但几何量测结果**逐档一致** —— 该设置只在「某行 height+depth ≥ baselineskip」时才起作用，
  而那种行的基线在 PDF 里取不准（行内分式的分子/分母各自是独立 span，其 origin 偏离真基线，
  会被读成 5.0/10.1pt 这种伪值）。
  **判据分辨不出真假，就不该留在里面冒充「机器保证」。** 那两行设置是否生效，只能靠
  破坏性实验确认（把 preamble 里对应行注释掉、比 `\\typeout` 输出），不能靠这个脚本。
  下面的 `below_main` 字段仍把低于主行距的档位列出来，**仅供参考，不判 FAIL**。

怎么识别「同一段内的相邻两行」——**靠首行缩进，不靠字体**：
    正文续行贴版心左边界（70.9pt = 25.0mm）；每段首行缩进 2em（≈94.8pt）。
    所以「当前行贴左边界」就说明它与上一行同段，两者基线之差才是真正的行距。
    按字体（宋体）筛行会把「以数学为主的行」整行漏掉 —— 而那种行
    恰恰是最容易触发回退的，于是判据永远报 PASS（假阴性）。
"""
import argparse, io, json, sys
from collections import Counter

try:
    import pymupdf
except ImportError:  # 旧包名
    import fitz as pymupdf

PT2MM = 25.4 / 72.0
NOMINAL_BASELINE = 19.9
BASELINE_TOL = 0.4
SQUEEZE_TOL = 0.6
MIN_NOMINAL_SHARE = 0.15   # 规范行距至少要占正文行距的 15%，低于此判 FAIL
MIN_PAIRS = 20             # 段内相邻行少于这个数就不做行距判定（避免拿 4 个样本误判）
MARGINS_MM = {"left": 25.0, "right": 21.8, "top": 24.2, "bottom": 13.5}
MARGIN_TOL_MM = 1.0
MARGIN_X_PT = 70.9          # 版心左边界（量测值），用于识别「续行」
INDENT_TOL_PT = 6.0         # 贴左边界的容差
TOP_BAND_MM = 22.0          # 正文上边界 24.2mm 再留 2mm 余量；整行在其上 = 页眉，不计入页边距


def measure(pdf_path, expect_margins=True):
    doc = pymupdf.open(pdf_path)
    diffs = Counter()
    body_lines = 0
    left_edges = Counter()      # 行左边缘的众数 = 正文左边界（比最小值稳，见下）
    miny = 1e9
    maxx = maxy = -1e9

    for pno in range(doc.page_count):
        lines = []
        for blk in doc[pno].get_text("dict")["blocks"]:
            if blk.get("type") != 0:
                continue
            for line in blk["lines"]:
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                # 行基线 = 该行各 span 的 origin 的**众数**（按字符数加权）。
                # 不能用 spans[0] 或「最长的 span」：行内的分式/上下标会各自成为一个
                # span，其 origin 偏离真正基线好几个点（分子偏高、分母偏低），
                # 直接取会被当成「行距」量出来 —— 会出现 0.1/3.2/5.0/35.8pt 这类伪值。
                # 真正坐在基线上的是占字符最多的那一层，取加权众数即得。
                votes = Counter()
                for s in spans:
                    votes[round(s["origin"][1], 2)] += len(s["text"].strip())
                s0_y = votes.most_common(1)[0][0]
                x0, y0, x1, y1 = line["bbox"]
                lines.append((s0_y, x0))
                # 页边距只统计**正文块**。带页眉的模板族（如 zh/default-latex）把页眉与
                # 横线排在版心上方、横线还向左伸出正文左边界 —— 直接取全场包围盒会把
                # 「左 20.1mm / 上 11.6mm」量成页边距，是纯假阳性。
                # 判据：整行都落在正文上边界之上的，一律是页眉，不计入。
                if y1 * PT2MM >= TOP_BAND_MM:
                    left_edges[round(x0 * PT2MM * 2) / 2] += 1     # 0.5mm 分辨率
                    miny = min(miny, y0)
                    maxx, maxy = max(maxx, x1), max(maxy, y1)
        # 同页内按基线自上而下排序；「当前行贴左边界」= 与上一行同段
        lines.sort()
        for (y_prev, _), (y_cur, x_cur) in zip(lines, lines[1:]):
            if abs(x_cur - MARGIN_X_PT) > INDENT_TOL_PT:
                continue                      # 段首行（缩进）→ 跨段，不计
            d = round(y_cur - y_prev, 1)
            if 0 < d < 60:
                diffs[d] += 1
        body_lines += len(lines)

    if not diffs:
        return {"status": "FAIL", "reason": "未采到段内相邻行（可能全是标题/公式/表格）",
                "pages": doc.page_count}

    total = sum(diffs.values())
    # 判据用「**规范值 19.9pt 的占比**」，不是「众数是不是 19.9」。
    #   公式密集的文档里，超高行（\dfrac、嵌套上下标）的间距会盖过正文行成为众数
    #   —— 一份压测样张的众数是 31.6pt，而正文行距其实完全正常。
    #   正文行在任何真实论文里都占大头，查它的占比既稳又切题。
    nominal_cnt = sum(c for v, c in diffs.items() if abs(v - NOMINAL_BASELINE) <= BASELINE_TOL)
    nominal_share = nominal_cnt / total
    main_val, main_cnt = diffs.most_common(1)[0]
    squeezed = {str(v): c for v, c in diffs.items() if v < main_val - SQUEEZE_TOL}
    page = doc[0].rect
    # left 取**众数**而不是最小值：代码附录的 listings 行号（numbers=left）会排到正文
    # 左边界之外几个毫米，取最小值会把「左 20.1mm」量成页边距。
    # 正文续行占绝对多数，众数即真正的版心左边界。
    left_mm = left_edges.most_common(1)[0][0] if left_edges else 0.0
    margins = {
        "left": round(left_mm, 1),
        "right": round((page.width - maxx) * PT2MM, 1),
        "top": round(miny * PT2MM, 1),
        "bottom": round((page.height - maxy) * PT2MM, 1),
    }

    issues, skipped = [], []
    # 样本太少时**不做判定**，而且不能把它塞进 issues —— 塞进去会让 status=FAIL，
    # 也就是把「没测」报成「不合格」：一份只有 4 对段内相邻行的文档会被判 FAIL，
    # 而它的行距完全正常。这与脚本自己「宁可不测，也不误判」的原则相反。
    # 现在单列到 `skipped`，status 仍按其余判据走（**页边距照常判**，它不依赖样本量）。
    enough = total >= MIN_PAIRS
    if not enough:
        skipped.append(f"行距判据样本不足（段内相邻行 {total} 对 < {MIN_PAIRS}），本次**不判定**")
    if enough and nominal_share < MIN_NOMINAL_SHARE:
        issues.append(f"规范行距 {NOMINAL_BASELINE}pt 只占正文行距的 {nominal_share:.1%}"
                      f"（下限 {MIN_NOMINAL_SHARE:.0%}；实见 {diffs.most_common(3)}）—— "
                      f"\\linespread / 刚性化设置可能被覆盖，或正文被大量超高行挤走")
    if expect_margins:
        for k, want in MARGINS_MM.items():
            if abs(margins[k] - want) > MARGIN_TOL_MM:
                issues.append(f"{k} 页边距 {margins[k]}mm 偏离实测模板值 {want}mm")

    return {
        "status": "FAIL" if issues else "PASS",
        "pages": doc.page_count,
        "body_lines": body_lines,
        "intra_paragraph_pairs": total,
        "main_baseline_pt": main_val,
        "nominal_share": round(nominal_share, 3),
        "main_baseline_share": round(main_cnt / total, 3),
        "distribution": {str(k): v for k, v in diffs.most_common(12)},
        "below_main": squeezed,   # 仅信息：低于主行距的档位（判据分辨不出真假，不判 FAIL）
        "margins_mm": margins,
        "issues": issues,
        "skipped": skipped,       # 因样本不足而**没测**的判据（不是通过，也不是失败）
        "note": "；".join(skipped),
    }


def main():
    ap = argparse.ArgumentParser(description="量 PDF 的行距刚性与页边距")
    ap.add_argument("pdf")
    ap.add_argument("--json")
    ap.add_argument("--no-margins", action="store_true",
                    help="跳过页边距检查（测非正文 PDF 时用）")
    args = ap.parse_args()
    result = measure(args.pdf, expect_margins=not args.no_margins)
    if args.json:
        io.open(args.json, "w", encoding="utf-8", newline="\n").write(
            json.dumps(result, ensure_ascii=False, indent=2))
    io.open(1, "w", encoding="utf-8", errors="replace").write(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""export_figure.py — 把 .drawio 导成 1:1 PNG 与矢量 PDF，供肉眼自检和交付。

    python3 export_figure.py fig.drawio                 # 出 fig.png + fig.pdf
    python3 export_figure.py fig.drawio --png-only -s 2 # 只出 2 倍图，便于看细节

依赖 draw.io 桌面版命令行（macOS: brew install --cask drawio；命令名 drawio）。
没装时会给出替代方案，不静默失败。
"""
import argparse
import pathlib
import re
import shutil
import subprocess
import sys

try:  # Windows 控制台/管道默认 GBK：中文判据直接 print 会 UnicodeEncodeError 崩掉，
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 而驱动会把崩溃当「脚本故障」静默放行
except Exception:
    pass


EXPORT_TIMEOUT = 300      # 秒；大图慢机器上不够就改这里（或命令行再说，别散落魔数）


def run(cmd):
    # `text=True` 必须配 `encoding`：不给的话 Python 按**进程 locale** 解码，
    #   Windows 中文机器上是 cp936。而下面这行会在失败时把 drawio 的**诊断**打出来，
    #   实参里又带着中文图路径 ⇒ 诊断里一出现非 GBK 能解的字节就抛 UnicodeDecodeError，
    #   脚本在最该说话的时候崩掉（驱动只会记一句"脚本故障"）。上面那句
    #   `sys.stdout.reconfigure` 防的是同一个坑的另一半，这里补上管道这一半。
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=EXPORT_TIMEOUT,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print(p.stdout + p.stderr, file=sys.stderr)
    return p.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('drawio')
    ap.add_argument('-s', '--scale', type=float, default=1, help='PNG 缩放，默认 1（1 单位=1 像素）')
    ap.add_argument('--png-only', action='store_true')
    ap.add_argument('--pdf-only', action='store_true')
    a = ap.parse_args()

    src = pathlib.Path(a.drawio)
    if not src.exists():
        sys.exit(f'找不到 {src}')
    cli = shutil.which('drawio')
    if not cli:
        sys.exit('未找到 drawio 命令行。\n'
                 '  macOS: brew install --cask drawio\n'
                 '  或：用 diagrams.net 网页版打开 .drawio 后 File → Export as → PNG/PDF\n'
                 '  注意：没有渲染图就无法自检，不要跳过这一步。')

    # 用画布宽度锁定输出，保证 1 单位 = 1 像素；否则 drawio 会按内容包围盒另算，
    # 输出比画布大几像素，没法和参考图做逐像素比对
    m = re.search(r'pageWidth="([\d.]+)"', src.read_text(encoding='utf-8'))
    width = [f'--width', str(int(float(m.group(1)) * a.scale))] if m else []

    # `--size page` = 导出**画布整页**，不是"内容包围盒"。
    #   为什么需要它：这些模板（`roadmap_5band` 等）的 954×1296 是**设计尺寸**，
    #   论文里的 `width_mm` 也是按**画布**长宽比定的。不给这个开关时，输出按内容包围盒算：
    #   `fig_roadmap` 若去掉那两个沿左+顶的实心浅灰底块，内容包围盒缩到 828×1242 ⇒
    #   **同一条命令**渲出来 PNG 变成 954×1431、PDF 的 MediaBox 变成 598×897 ⇒
    #   论文里同宽（163.8 mm）下高度由 222 mm 涨到 246 mm，而版心高只有 250 mm ⇒
    #   整栏图连图注一起放不下一页。加上 `--size page` 后：PNG 954×1297、
    #   PDF 687.12×932.88（旧 `--crop` 是 688.08×934.08，差 0.14%、长宽比一致）。
    #   注意：PNG 侧 `--size page` **必须配 `--width`**：只给 `--size page` 会得到 956×1298
    #   （多出的 2 px 是边框取整），与参考件的 1 单位 = 1 像素对不上。
    ok = True
    if not a.pdf_only:
        png = src.with_suffix('.png')
        ok &= run([cli, '-x', '-f', 'png', '-s', str(a.scale), '-b', '0',
                   *width, '--size', 'page', '-o', str(png), str(src)])
        if ok:
            print(f'✓ {png}')
    if not a.png_only:
        pdf = src.with_suffix('.pdf')
        ok &= run([cli, '-x', '-f', 'pdf', '--size', 'page', '-o', str(pdf), str(src)])
        if ok:
            print(f'✓ {pdf}')
    if not ok:
        sys.exit(1)
    print('接下来务必打开 PNG 逐块核对：文字有无溢出/压线、箭头方向、数值有没有抄错。')


if __name__ == '__main__':
    main()

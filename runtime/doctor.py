"""Read-only dependency check; never install packages or launch models."""
import importlib
import importlib.metadata
import json
import shutil
import sys
from pathlib import Path

PACKAGES = {
    "numpy": "numpy", "scipy": "scipy", "pandas": "pandas", "matplotlib": "matplotlib",
    "sympy": "sympy", "sklearn": "scikit-learn", "openpyxl": "openpyxl", "pymupdf": "PyMuPDF",
    "PIL": "Pillow", "fastapi": "fastapi", "uvicorn": "uvicorn", "pydantic": "pydantic",
    "multipart": "python-multipart", "httpx": "httpx",
}


def claude_status():
    """`claude` 可执行文件在不在 —— 与驱动**共用同一份实现**（`lib/web/claude_bin.py`）。

    为什么必须有这一项：驱动是在 **import 期**发现找不到 claude 就地退出的，而本脚本
      只看 Python 包与外部工具 ⇒ 查不出"doctor 全绿、驱动却起不来"这种组合。发现逻辑
      不在这里重写一遍，免得两处迟早漂移。

    用 `sys.path` 指到 `lib/web` 再 import：那个模块**无副作用**（不建目录、不读 .env、
      不 sys.exit），import 它是安全的；而 `server.py` 绝不能在 CLI 里 import ——
      它会拉起 FastAPI 并执行模块级副作用（仓库里所有 CLI 都守着这条）。
    """
    here = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(here / "lib" / "web"))
    try:
        from claude_bin import doctor_report
    except Exception as exc:                      # noqa: BLE001 —— 报出来即可，别让 doctor 自己崩
        return {"status": "UNKNOWN", "detail": f"读不到 lib/web/claude_bin.py：{exc}"}
    return doctor_report()


def main():
    results, missing = {}, []
    for module, package in PACKAGES.items():
        try:
            importlib.import_module(module)
            results[package] = {"status": "OK", "version": importlib.metadata.version(package)}
        except Exception as exc:
            results[package] = {"status": "MISSING_OR_BROKEN", "error": str(exc)}
            missing.append(package)
    claude = claude_status()
    if claude.get("status") != "OK":
        # 与其余缺失项分开列：它缺了是**驱动根本起不来**（import 期 SystemExit），
        #   不是"某个功能用不了"，严重程度不一样，混在一起会被当成可选依赖划过去。
        missing.append("claude")
    print(json.dumps({"python": sys.executable, "packages": results, "missing": missing,
                      "claude": claude,
                      "external_tools": {name: (shutil.which(name) or (shutil.which("draw.io") if name == "drawio" else None))
                                         for name in ("xelatex", "pdftoppm", "pandoc", "drawio")},
                      "note": "DrawIO/Pandoc are optional. Missing xelatex blocks LaTeX compilation. "
                              "Missing claude means the driver will not start at all. No installation performed."},
                     ensure_ascii=True, indent=2))
    return bool(missing)


if __name__ == "__main__":
    raise SystemExit(main())

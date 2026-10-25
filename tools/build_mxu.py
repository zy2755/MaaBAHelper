"""MXU 分发目录一键同步/打包。

解决"改了源目录忘同步 MXU"的历史 bug：从 MaaBAHelper 镜像 agent/interface/resource
到 ../MXU，校验一致后可选 --zip 打包（剔除运行时垃圾与 313MB 的 pdb）。

用法：
    python tools/build_mxu.py            # 同步 + 校验
    python tools/build_mxu.py --zip      # 同步 + 校验 + 打包 dist/MXU_<日期>.zip
    python tools/build_mxu.py --mxu D:/somewhere/MXU   # 指定其他分发目录
"""

import argparse
import filecmp
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 源 → 目标 的镜像关系（相对 ROOT）
SYNC_MAP = [
    (ROOT / "agent", "agent"),
    (ROOT / "assets" / "interface.json", "interface.json"),
    (ROOT / "assets" / "resource", "resource"),
]

IGNORE_DIRS = {"__pycache__"}          # 镜像时忽略（不复制、不删除）
ZIP_EXCLUDE_DIRS = {"cache", "config", "debug", "__pycache__"}
ZIP_EXCLUDE_SUFFIXES = {".pdb", ".log"}


def iter_files(base: Path):
    for p in base.rglob("*"):
        if p.is_file() and not (set(p.parts) & IGNORE_DIRS):
            yield p


def mirror(src: Path, dst: Path) -> int:
    """src 镜像到 dst（只复制有变化的，删除 dst 中 src 已不存在的）。返回复制数。"""
    copied = 0
    src_files = {p.relative_to(src): p for p in iter_files(src)}
    for rel, s in src_files.items():
        d = dst / rel
        if not d.exists() or not filecmp.cmp(s, d, shallow=False):
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
            copied += 1
            print(f"  + {rel}")
    for p in iter_files(dst):
        rel = p.relative_to(dst)
        if rel not in src_files:
            p.unlink()
            print(f"  - {rel}")
    # 清掉空目录（保留 dst 本身）
    for d in sorted((x for x in dst.rglob("*") if x.is_dir()), reverse=True):
        if not (set(d.parts) & IGNORE_DIRS) and not any(d.iterdir()):
            d.rmdir()
    return copied


def verify(pairs) -> bool:
    ok = True
    for src, dst in pairs:
        if src.is_file():
            if not (dst.exists() and filecmp.cmp(src, dst, shallow=False)):
                print(f"  ✗ {dst} 不一致")
                ok = False
            continue
        src_files = {p.relative_to(src): p for p in iter_files(src)}
        dst_files = {p.relative_to(dst): p for p in iter_files(dst)}
        for rel in sorted(src_files.keys() | dst_files.keys()):
            if rel not in dst_files or rel not in src_files:
                print(f"  ✗ {dst.name}/{rel} 缺失")
                ok = False
            elif not filecmp.cmp(src_files[rel], dst_files[rel], shallow=False):
                print(f"  ✗ {dst.name}/{rel} 内容不一致")
                ok = False
    return ok


def make_zip(mxu: Path) -> Path:
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / f"MXU_{date.today():%Y%m%d}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in mxu.rglob("*"):
            if not p.is_file():
                continue
            parts = set(p.relative_to(mxu).parts)
            if parts & ZIP_EXCLUDE_DIRS or p.suffix in ZIP_EXCLUDE_SUFFIXES:
                continue
            zf.write(p, p.relative_to(mxu.parent))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mxu", default=str(ROOT.parent / "MXU"))
    ap.add_argument("--zip", action="store_true", help="同步校验后打包")
    args = ap.parse_args()
    mxu = Path(args.mxu)
    if not mxu.is_dir():
        sys.exit(f"MXU 目录不存在: {mxu}")

    pairs = []
    for src, rel in SYNC_MAP:
        if not src.exists():
            sys.exit(f"源不存在: {src}")
        dst = mxu / rel
        if src.is_dir():
            print(f"[sync] {src.name}/ -> {dst}")
            n = mirror(src, dst)
            print(f"  共复制 {n} 个文件")
            pairs.append((src, dst))
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not (dst.exists() and filecmp.cmp(src, dst, shallow=False)):
                shutil.copy2(src, dst)
                print(f"[sync] {src.name} -> {dst} (更新)")
            else:
                print(f"[sync] {src.name} 无变化")
            pairs.append((src, dst))

    print("[verify] 校验镜像一致性...")
    if not verify(pairs):
        sys.exit("✗ 校验失败，MXU 与源不一致")
    print("  ✓ 一致")

    if args.zip:
        out = make_zip(mxu)
        size = out.stat().st_size / 1024 / 1024
        print(f"[zip] {out} ({size:.1f} MB)")


if __name__ == "__main__":
    main()

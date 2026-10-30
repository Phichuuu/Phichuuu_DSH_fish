#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把手机截图压成能进模型的尺寸。

为什么需要它
------------
MuMu 里 900x1600 的 PNG 截图有 2.5 MB，base64 后 3.4 MB —— 一个图片块就把
上下文撑爆了，而且视觉模型对超过 1 MB 的图通常也没更多收益。

做法：长边缩到 900 以内，转 JPEG（质量 80）。2.5 MB -> 大约 150~250 KB，
屏幕上该看清的字仍然看得清。

用法：
    python shrink-shot.py <输入.png> <输出.jpg>
    成功打印输出路径，失败打印原因并返回非零退出码。
"""

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print('用法: shrink-shot.py <输入> <输出.jpg>', file=sys.stderr)
        return 2

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])

    if not src.is_file():
        print(f'找不到输入文件: {src}', file=sys.stderr)
        return 3

    try:
        from PIL import Image
    except Exception as e:  # pragma: no cover - 环境缺 Pillow 才会走到
        print(f'缺少 Pillow: {e}', file=sys.stderr)
        return 4

    try:
        with Image.open(src) as im:
            im = im.convert('RGB')
            w, h = im.size
            longest = max(w, h)
            if longest > 900:
                scale = 900.0 / longest
                im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
            dst.parent.mkdir(parents=True, exist_ok=True)
            im.save(dst, 'JPEG', quality=80, optimize=True)
    except Exception as e:
        print(f'转换失败: {e}', file=sys.stderr)
        return 5

    print(dst)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

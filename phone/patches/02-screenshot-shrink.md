# 补丁 2 · 截图太大

## 症状

`phone_screenshot` 返回的图片有 **1.3–2.5 MB**（900×1600 PNG），
base64 编码后约 1.8–3.4 MB。

一个图片块就能吃掉几万 token，多来几张上下文直接爆。

## 原因

上游是直接把 PNG 原样 base64 塞进 MCP 响应里的：

```js
const bytes = fs.statSync(local).size;
const content = [{ type: 'text', text: `截图已保存: ${local} (${bytes} 字节)` }];
if (bytes > 0 && bytes < 4 * 1024 * 1024) {          // 只挡"太大"，但 2.5MB 也算"不大"
  content.push({ type: 'image', data: fs.readFileSync(local).toString('base64'), mimeType: 'image/png' });
}
```

## 修法

返回前压成 JPEG（长边 ≤ 900，质量 80）→ **60~250 KB**，字还是清楚的。

### 1. 加一个压缩辅助函数

放在 `runFfmpeg` 附近：

```js
const SHRINK_PYTHON = process.env.PHONE_PYTHON || 'python';
const SHRINK_SCRIPT = process.env.PHONE_SHRINK_SCRIPT || '<repo>/voice/shrink-shot.py';

async function shrinkShot(pngPath) {
  try {
    if (!fs.existsSync(SHRINK_PYTHON) || !fs.existsSync(SHRINK_SCRIPT)) return null;
    const jpgPath = pngPath.replace(/\.png$/i, '.jpg') + '.shrunk.jpg';
    const r = await new Promise((resolve) => {
      execFile(SHRINK_PYTHON, [SHRINK_SCRIPT, pngPath, jpgPath],
        { timeout: 30000, windowsHide: true },
        (err, stdout, stderr) => resolve({ ok: !err, out: String(stdout ?? ''), err: String(stderr ?? err?.message ?? '') }));
    });
    if (!r.ok || !fs.existsSync(jpgPath)) return null;
    return jpgPath;
  } catch { return null; }
}
```

### 2. 改 `phone_screenshot`

```diff
  const bytes = fs.statSync(local).size;
  const content = [{ type: 'text', text: `截图已保存: ${local} (${bytes} 字节)` }];
- if (bytes > 0 && bytes < 4 * 1024 * 1024) {
-   content.push({ type: 'image', data: fs.readFileSync(local).toString('base64'), mimeType: 'image/png' });
+ let imgPath = local, imgMime = 'image/png';
+ if (bytes > 400 * 1024) {
+   const shrunk = await shrinkShot(local);
+   if (shrunk) { imgPath = shrunk; imgMime = 'image/jpeg'; }
+ }
+ const imgBytes = fs.statSync(imgPath).size;
+ if (imgBytes > 0 && imgBytes < 1.6 * 1024 * 1024) {
+   content.push({ type: 'image', data: fs.readFileSync(imgPath).toString('base64'), mimeType: imgMime });
  }
  return { content };
```

### 3. `voice/shrink-shot.py`

用 Pillow 实现（大多数 Python 环境都有；没有就 `pip install pillow`）：

```python
from PIL import Image
im = Image.open(src).convert('RGB')
im.thumbnail((900, 900), Image.LANCZOS)   # 长边 ≤ 900
im.save(dst, 'JPEG', quality=80, optimize=True)
```

## 效果

| 场景 | 原 PNG | 压缩后 |
|---|---|---|
| 桌面 | 1.35 MB | 60 KB |
| 应用商店 | 2.31 MB | ~120 KB |
| 视频/游戏画面 | 2.5 MB+ | 150~250 KB |

## 为什么不用 ffmpeg 压

能用，但为了**一张截图**去起一个 ffmpeg 进程太重（还得额外装 ffmpeg）。
Pillow 更轻，而且 `shrink-shot.py` 本来就要给别的脚本复用。

ffmpeg 只在 `phone_record_screen` / `video_frames` 里需要。

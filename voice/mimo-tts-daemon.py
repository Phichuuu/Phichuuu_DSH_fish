#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""小米 MiMo TTS 常驻服务（OpenAI 兼容接口）。

为什么换成它
------------
本地两条路都不理想：
  · edge-tts + RVC  —— RVC 只换音色，换不掉合成嗓的节奏与呼吸缺失
  · 本地 CosyVoice3 —— 依赖链折腾通了，但 prompt_text 与参考音不匹配，
                       短句会触发 "too short" 降质，听感仍然怪
MiMo 是在服务端做 TTS，音质与风格控制（情绪/方言/唱歌标签）都强得多，
于是把它接成同一条 HTTP 形态，上层 MCP 只换地址。

接口（只监听 127.0.0.1）
    GET  /health
    POST /say {"text": "...", "mode": "clone"|"preset", "voice": "冰糖", "style": "温柔"}
         -> {"ok": true, "file": "mimo_xxx.wav", "seconds": 3.2, "took_ms": 4200}

    mode=clone  用 references/cute_N01.wav 克隆肥鱼音色（不支持唱歌）
    mode=preset 用预置音色（支持 (唱歌) 等标签）

产物写进 F:\\qq-bridge\\audio，桥接的 qq_send_voice 直接能认。
API Key 从 MIMO_API_KEY 环境变量或 F:\\feiyu-voice\\mimo-key.txt 读取。
"""

import base64
import json
import os
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_URL = os.environ.get("MIMO_API_URL", "https://api.xiaomimimo.com/v1/chat/completions")
OUT_DIR = Path(os.environ.get("MIMO_OUT_DIR", r"F:\qq-bridge\audio"))
REF_AUDIO = Path(os.environ.get("MIMO_REF_AUDIO", r"F:\feiyu-voice\cosyvoice-models\references\cute_N01.wav"))
KEY_FILE = Path(os.environ.get("MIMO_KEY_FILE", r"F:\feiyu-voice\mimo-key.txt"))
PORT = int(os.environ.get("MIMO_PORT", "8850"))

MODEL_CLONE = "mimo-v2.5-tts-voiceclone"
MODEL_PRESET = "mimo-v2.5-tts"
MODEL_DESIGN = "mimo-v2.5-tts-voicedesign"

DEFAULT_STYLE_CLONE = (
    "用一条有点懒、有点黏人的年轻女孩子的声音说话，语速中等偏慢，"
    "尾音轻轻上翘，偶尔带一点点气声，像在跟很熟的人撒娇。不要播音腔。"
)
DEFAULT_STYLE_PRESET = "活泼俏皮，带一点小得意，像在跟熟人聊天"

# voicedesign：这段就是"造音色"的描述，越具体越稳。
DEFAULT_STYLE_DESIGN = (
    "十几岁的少女声音，音色清甜偏细，带一点点鼻音和颗粒感。"
    "说话像在跟很熟的人撒娇，尾音习惯性轻轻上扬，句末常常拖一点点，"
    "时不时有一个软软的气声。不要播音腔，不要字正腔圆，"
    "要那种一听就知道在耍小性子、但其实心里是高兴的『娇』。"
)


def log(msg: str) -> None:
    print(f"[mimo-tts] {msg}", flush=True)


def load_key() -> str:
    key = os.environ.get("MIMO_API_KEY", "").strip()
    if key:
        return key
    try:
        return KEY_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def ref_b64() -> str:
    """voiceclone 要的是 DataURL，不是裸 base64（API 原文：audio.voice must be a DataURL）"""
    raw = base64.b64encode(REF_AUDIO.read_bytes()).decode("ascii")
    suffix = REF_AUDIO.suffix.lower().lstrip(".") or "wav"
    mime = "mpeg" if suffix == "mp3" else suffix
    return f"data:audio/{mime};base64,{raw}"


def synthesize(text: str, mode: str = "clone", voice: str = "", style: str = "") -> dict:
    started = time.time()
    key = load_key()
    if not key:
        raise RuntimeError("没有 MiMo API Key：设 MIMO_API_KEY 或写进 F:\\feiyu-voice\\mimo-key.txt")

    mode = (mode or "clone").lower()
    if mode == "preset":
        model = MODEL_PRESET
        user_style = style.strip() or DEFAULT_STYLE_PRESET
        audio_opts = {"format": "wav", "voice": voice.strip() or "冰糖"}
    elif mode == "design":
        # voicedesign：user 消息就是"音色描述"，assistant 是要合成的文本。
        model = MODEL_DESIGN
        user_style = style.strip() or DEFAULT_STYLE_DESIGN
        audio_opts = {"format": "wav"}
    else:
        model = MODEL_CLONE
        user_style = style.strip() or DEFAULT_STYLE_CLONE
        audio_opts = {"format": "wav", "voice": ref_b64()}

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": user_style},
            {"role": "assistant", "content": text},
        ],
        "audio": audio_opts,
        "stream": False,
    }

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "api-key": key,
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=180) as resp:
        body = json.loads(resp.read().decode("utf-8", "replace"))

    audio = (((body.get("choices") or [{}])[0].get("message") or {}).get("audio") or {})
    data = audio.get("data")
    if not data:
        raise RuntimeError(f"响应里没有音频：{json.dumps(body, ensure_ascii=False)[:300]}")

    raw = base64.b64decode(data)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    final = OUT_DIR / f"mimo_{stamp}.wav"
    final.write_bytes(raw)

    seconds = 0.0
    try:
        import soundfile as sf

        seconds = round(float(sf.info(str(final)).duration), 2)
    except Exception:
        seconds = round(len(raw) / 48000.0, 2)  # 粗估

    return {
        "ok": True,
        "file": final.name,
        "mode": mode,
        "model": model,
        "seconds": seconds,
        "took_ms": int((time.time() - started) * 1000),
    }


PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>肥鱼语音试听</title>
<style>
:root{color-scheme:dark}
body{font:15px/1.6 system-ui,"Microsoft YaHei",sans-serif;background:#0f1216;color:#e6edf3;
     max-width:760px;margin:40px auto;padding:0 20px}
h1{font-size:20px;margin-bottom:4px}
.sub{color:#8b949e;font-size:13px;margin-bottom:24px}
label{display:block;margin:16px 0 6px;color:#9da7b3;font-size:13px}
textarea,input,select{width:100%;background:#161b22;border:1px solid #30363d;color:#e6edf3;
     border-radius:8px;padding:10px;font:inherit;box-sizing:border-box}
textarea{height:96px;resize:vertical}
.row{display:flex;gap:12px}.row>div{flex:1}
button{margin-top:20px;width:100%;padding:12px;border:0;border-radius:8px;background:#2f81f7;
     color:#fff;font-size:15px;font-weight:600;cursor:pointer}
button:disabled{background:#30363d;color:#8b949e;cursor:wait}
#out{margin-top:20px}
audio{width:100%;margin-top:10px}
#msg{margin-top:12px;font-size:13px;color:#8b949e;white-space:pre-wrap}
</style></head><body>
<h1>&#128051; 肥鱼语音试听</h1>
<div class="sub">本地服务 · MiMo TTS · 说话走克隆音色，唱歌走预置音色</div>

<label>要说的话</label>
<textarea id="text">主人，这回是我自己的声音啦。你听听，像不像一条鱼？</textarea>

<div class="row">
  <div><label>模式</label>
    <select id="mode">
      <option value="clone">说话（克隆肥鱼音色）</option>
      <option value="preset">说话（预置音色）</option>
      <option value="sing">唱歌（自动加 (唱歌) 标签）</option>
    </select>
  </div>
  <div><label>预置音色</label>
    <select id="voice">
      <option>冰糖</option><option>茉莉</option><option>苏打</option><option>白桦</option>
      <option>Mia</option><option>Chloe</option><option>Milo</option><option>Dean</option>
    </select>
  </div>
</div>

<label>语气提示（可选）</label>
<input id="style" placeholder="例如：温柔一点；撒个娇；有点困">

<button id="go">合成并播放</button>
<div id="out"></div>
<div id="msg"></div>

<script>
const $ = (id) => document.getElementById(id);
$('go').onclick = async () => {
  $('go').disabled = true;
  $('msg').textContent = '合成中…（一般 2~8 秒）';
  $('out').innerHTML = '';
  try {
    const res = await fetch('/say', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: $('text').value,
        mode: $('mode').value,
        voice: $('voice').value,
        style: $('style').value,
      }),
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || ('HTTP ' + res.status));
    const audio = document.createElement('audio');
    audio.controls = true;
    audio.autoplay = true;
    audio.src = '/audio/' + encodeURIComponent(data.file) + '?t=' + Date.now();
    $('out').appendChild(audio);
    $('msg').textContent = data.file + ' · ' + data.seconds + ' 秒 · 用时 ' +
      Math.round((data.took_ms || 0) / 1000) + ' 秒 · ' + (data.model || '');
  } catch (e) {
    $('msg').textContent = '失败：' + e.message;
  } finally {
    $('go').disabled = false;
  }
};
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_audio(self, path: Path) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send_html(PAGE)
            return
        if self.path.startswith("/audio/"):
            name = urllib.parse.unquote(self.path.split("/audio/", 1)[1].split("?", 1)[0])
            target = (OUT_DIR / name).resolve()
            try:
                target.relative_to(OUT_DIR.resolve())
            except Exception:
                self._send(403, {"ok": False, "error": "越界"})
                return
            if target.is_file():
                self._send_audio(target)
            else:
                self._send(404, {"ok": False, "error": "没有这个文件"})
            return
        if self.path.startswith("/health"):
            self._send(200, {
                "ok": True,
                "engine": "MiMo-TTS",
                "hasKey": bool(load_key()),
                "refAudio": REF_AUDIO.is_file(),
                "port": PORT,
            })
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/say"):
            self._send(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")
            text = str(data.get("text") or "").strip()
            if not text:
                self._send(400, {"ok": False, "error": "text 为空"})
                return
            if len(text) > 1000:
                self._send(400, {"ok": False, "error": "太长（上限 1000 字）"})
                return
            self._send(200, synthesize(
                text,
                mode=str(data.get("mode") or "clone"),
                voice=str(data.get("voice") or ""),
                style=str(data.get("style") or ""),
            ))
        except Exception as e:
            log(f"error: {e}")
            self._send(500, {"ok": False, "error": str(e)})


def main() -> int:
    log(f"api={API_URL}")
    log(f"key={'yes' if load_key() else 'NO'}")
    log(f"ref={REF_AUDIO} ({'ok' if REF_AUDIO.is_file() else 'missing'})")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    log(f"listening http://127.0.0.1:{PORT}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

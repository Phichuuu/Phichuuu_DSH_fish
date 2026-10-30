#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MiniMax（海螺）TTS 常驻服务。

为什么换到 MiniMax
------------------
TTS 的听感顺序大致是：真人录音 > 一线商用 TTS > 本地小模型 > RVC 换声。
MiMo 的 voicedesign 靠文字"想象"音色，天生带一点表演感；MiniMax 的系统音色
（lovely_girl / Crisp_Girl / female-shaonv 等）是真人录制的，自然度高一个档。

接口（只监听 127.0.0.1）
    GET  /            试听页
    GET  /health
    POST /say {"text": "...", "voice": "lovely_girl", "emotion": "happy",
               "speed": 1.0, "pitch": 0}
         -> {"ok": true, "file": "mm_xxx.mp3", "seconds": 3.2}

注意：MiniMax 的响应里 audio 是 **hex 编码**，不是 base64（踩过）。
Key 从 MINIMAX_API_KEY 环境变量或 F:\\feiyu-voice\\minimax-key.txt 读取。
"""

import json
import os
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_URL = os.environ.get("MINIMAX_API_URL", "https://api.minimax.cn/v1/t2a_v2")
OUT_DIR = Path(os.environ.get("MINIMAX_OUT_DIR", r"F:\qq-bridge\audio"))
KEY_FILE = Path(os.environ.get("MINIMAX_KEY_FILE", r"F:\feiyu-voice\minimax-key.txt"))
PORT = int(os.environ.get("MINIMAX_PORT", "8851"))

MODEL = os.environ.get("MINIMAX_MODEL", "speech-2.8-hd")
DEFAULT_VOICE = os.environ.get("MINIMAX_VOICE", "female-shaonv")  # 2026-10-27 主人选定的音色

# 可爱向的音色（来自系统音色列表）
CUTE_VOICES = [
    ("lovely_girl", "萌萌女童"),
    ("Chinese (Mandarin)_Crisp_Girl", "清脆少女"),
    ("female-shaonv", "少女音色"),
    ("female-tianmei", "甜美女性"),
    ("female-yujie", "御姐音色"),
    ("Chinese (Mandarin)_Gentle_Senior", "温柔学姐"),
    ("male-qn-qingse", "青涩青年"),
]


def log(msg: str) -> None:
    print(f"[minimax-tts] {msg}", flush=True)


def load_key() -> str:
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if key:
        return key
    try:
        return KEY_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def synthesize(text: str, voice: str = "", emotion: str = "", speed: float = 1.05,
               pitch: int = 2, model: str = "") -> dict:
    started = time.time()
    key = load_key()
    if not key:
        raise RuntimeError("没有 MiniMax API Key：设 MINIMAX_API_KEY 或写进 F:\\feiyu-voice\\minimax-key.txt")

    use_model = (model or MODEL).strip()
    voice_setting = {
        "voice_id": (voice or DEFAULT_VOICE).strip(),
        "speed": float(speed if speed is not None else 1.05),
        "vol": 1.0,
        "pitch": int(pitch or 0),
    }
    if emotion:
        voice_setting["emotion"] = emotion

    payload = {
        "model": use_model,
        "text": text,
        "stream": False,
        "voice_setting": voice_setting,
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
        "subtitle_enable": False,
    }

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"HTTP {e.code}: {detail}")

    base_resp = body.get("base_resp") or {}
    if base_resp.get("status_code") not in (0, None):
        raise RuntimeError(f"接口报错 {base_resp.get('status_code')}: {base_resp.get('status_msg')}")

    hex_audio = ((body.get("data") or {}).get("audio") or "").strip()
    if not hex_audio:
        raise RuntimeError(f"响应里没有音频：{json.dumps(body, ensure_ascii=False)[:250]}")

    raw = bytes.fromhex(hex_audio)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    final = OUT_DIR / f"mm_{stamp}.mp3"
    final.write_bytes(raw)

    info = body.get("extra_info") or {}
    seconds = round(float(info.get("audio_length") or 0) / 1000.0, 2)

    return {
        "ok": True,
        "file": final.name,
        "model": use_model,
        "voice": voice_setting["voice_id"],
        "seconds": seconds,
        "took_ms": int((time.time() - started) * 1000),
    }


PAGE_TMPL = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>MiniMax 语音试听</title>
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
button:disabled{background:#30363d;color:#8b949e}
audio{width:100%;margin-top:10px}
#msg{margin-top:12px;font-size:13px;color:#8b949e;white-space:pre-wrap}
</style></head><body>
<h1>&#128051; MiniMax 语音试听</h1>
<div class="sub">__STATUS__</div>
<label>要说的话</label>
<textarea id="text">主人主人，你看我今天乖不乖呀</textarea>
<div class="row">
  <div><label>音色</label><select id="voice">__VOICES__</select></div>
  <div><label>情绪</label><select id="emotion">
    <option value="">（不指定）</option><option value="happy">happy 开心</option>
    <option value="sad">sad 难过</option><option value="angry">angry 生气</option>
    <option value="fearful">fearful 害怕</option><option value="disgusted">disgusted 厌恶</option>
    <option value="surprised">surprised 惊讶</option><option value="neutral">neutral 平静</option>
  </select></div>
</div>
<div class="row">
  <div><label>语速（0.5~2）</label><input id="speed" value="1.0"></div>
  <div><label>音调（-12~12）</label><input id="pitch" value="2"></div>
</div>
<button id="go">合成并播放</button>
<div id="out"></div><div id="msg"></div>
<script>
const $ = (id) => document.getElementById(id);
$('go').onclick = async () => {
  $('go').disabled = true; $('msg').textContent = '合成中…'; $('out').innerHTML = '';
  try {
    const res = await fetch('/say', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({text:$('text').value, voice:$('voice').value,
        emotion:$('emotion').value, speed:parseFloat($('speed').value)||1.0,
        pitch:parseInt($('pitch').value)||0})});
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || ('HTTP ' + res.status));
    const a = document.createElement('audio');
    a.controls = true; a.autoplay = true;
    a.src = '/audio/' + encodeURIComponent(data.file) + '?t=' + Date.now();
    $('out').appendChild(a);
    $('msg').textContent = data.file + ' · ' + data.seconds + ' 秒 · ' + data.model + ' · ' + data.voice;
  } catch (e) { $('msg').textContent = '失败：' + e.message; }
  finally { $('go').disabled = false; }
};
</script></body></html>
"""


def render_page() -> str:
    voices = "".join(
        f'<option value="{vid}">{label}（{vid}）</option>' for vid, label in CUTE_VOICES
    )
    status = "已配置 API Key" if load_key() else "⚠️ 还没有 API Key —— 写进 F:\\feiyu-voice\\minimax-key.txt"
    return PAGE_TMPL.replace("__VOICES__", voices).replace("__STATUS__", status)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, ctype: str, data: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._bytes("text/html; charset=utf-8", render_page().encode("utf-8"))
            return
        if self.path.startswith("/audio/"):
            name = self.path.split("/audio/", 1)[1].split("?", 1)[0]
            target = (OUT_DIR / name).resolve()
            try:
                target.relative_to(OUT_DIR.resolve())
            except Exception:
                self._json(403, {"ok": False, "error": "越界"})
                return
            if target.is_file():
                self._bytes("audio/mpeg", target.read_bytes())
            else:
                self._json(404, {"ok": False, "error": "没有这个文件"})
            return
        if self.path.startswith("/health"):
            self._json(200, {"ok": True, "engine": "MiniMax-TTS", "hasKey": bool(load_key()), "model": MODEL, "port": PORT})
            return
        self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/say"):
            self._json(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")
            text = str(data.get("text") or "").strip()
            if not text:
                self._json(400, {"ok": False, "error": "text 为空"})
                return
            if len(text) > 2000:
                self._json(400, {"ok": False, "error": "太长（上限 2000 字）"})
                return
            self._json(200, synthesize(
                text,
                voice=str(data.get("voice") or ""),
                emotion=str(data.get("emotion") or ""),
                speed=float(data["speed"]) if data.get("speed") not in (None, "") else 1.05,
                pitch=int(data["pitch"]) if data.get("pitch") not in (None, "") else 2,
                model=str(data.get("model") or ""),
            ))
        except Exception as e:
            log(f"error: {e}")
            self._json(500, {"ok": False, "error": str(e)})


def main() -> int:
    log(f"api={API_URL} model={MODEL}")
    log(f"key={'yes' if load_key() else 'NO'}")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    log(f"listening http://127.0.0.1:{PORT}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

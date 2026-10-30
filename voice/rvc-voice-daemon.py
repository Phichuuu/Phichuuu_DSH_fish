#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""常驻语音服务：文字 -> edge-tts -> RVC 音色 -> 落盘到 QQ 桥接的语音库。

为什么要有它
------------
直接用 `python -m infer.cli` 转一句话要 50 秒，其中 40 多秒都花在**每次重新加载
RVC 模型和 hubert** 上。这里把模型 load 一次常驻，之后每句只剩合成时间（几秒）。

接口
----
    GET  /health                 -> {"ok": true, "model": "tomori", "device": "cuda:0"}
    POST /say  {"text": "...", "pitch": 0, "index_rate": 0.75}
         -> {"ok": true, "file": "tts_xxxx.wav", "seconds": 3.2, "took_ms": 4200}

输出文件写进 OUT_DIR（默认 F:\\qq-bridge\\audio），桥接的 qq_send_voice 直接能认。

只监听 127.0.0.1，不对外。
"""

import asyncio
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RVC_ROOT = Path(r"F:\RVC\RVC")
OUT_DIR = Path(os.environ.get("VOICE_OUT_DIR", r"F:\qq-bridge\audio"))
TMP_DIR = Path(r"F:\RVC\tmp")
PORT = int(os.environ.get("VOICE_PORT", "8848"))
MODEL = os.environ.get("VOICE_MODEL", "FeiyuVoice-RVC-v1.pth")
INDEX = os.environ.get("VOICE_INDEX", r"F:\RVC\RVC\logs\FeiyuVoice-RVC-v1.index")
TTS_VOICE = os.environ.get("VOICE_TTS", "zh-CN-XiaoxiaoNeural")

# 与 infer/cli.py 一致的环境准备
os.chdir(RVC_ROOT)
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("weight_root", str(RVC_ROOT / "assets" / "weights"))
os.environ.setdefault("index_root", str(RVC_ROOT / "logs"))
os.environ.setdefault("outside_index_root", str(RVC_ROOT / "assets" / "indices"))
os.environ.setdefault("rmvpe_root", str(RVC_ROOT / "assets" / "rmvpe"))

sys.path.insert(0, str(RVC_ROOT))

_vc = None
_config = None


def log(msg: str) -> None:
    print(f"[voice-daemon] {msg}", flush=True)


def load_model():
    """加载一次 VC，之后所有请求复用。"""
    global _vc, _config
    if _vc is not None:
        return _vc

    from configs.config import Config
    from infer.vc.modules import VC

    # 和 infer/cli.py 的 create_config() 一致：Config() 内部会解析 sys.argv，
    # 常驻进程里不能让它看到别的东西，否则 argparse 会直接退出。
    original_argv = sys.argv[:]
    sys.argv = [sys.argv[0]]
    try:
        _config = Config()
    finally:
        sys.argv = original_argv

    # get_vc 收的是"模型文件名"，目录由 weight_root 决定（同样照 cli.py 的做法）
    model_path = (RVC_ROOT / "assets" / "weights" / MODEL).resolve()
    os.environ["weight_root"] = str(model_path.parent)
    log(f"device={_config.device} dtype={_config.dtype}")
    vc = VC(_config)
    vc.get_vc(model_path.name)
    _vc = vc
    log(f"model ready: {model_path.name}")
    return vc


async def _tts(text: str, out_path: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, TTS_VOICE)
    await communicate.save(str(out_path))


def synthesize(text: str, pitch: int = 0, index_rate: float = 0.3) -> dict:
    started = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    raw = TMP_DIR / f"tts_{stamp}.mp3"
    final = OUT_DIR / f"tts_{stamp}.wav"

    asyncio.run(_tts(text, raw))

    vc = load_model()
    status, result = vc.vc_single(0, str(raw), pitch, "rmvpe", INDEX, index_rate, 0, 1.0, 0.33)
    if not result or result[1] is None:
        raise RuntimeError(f"RVC 转换失败: {status}")

    import soundfile as sf

    audio = result[1]
    sr = result[0]
    sf.write(str(final), audio, sr)

    try:
        raw.unlink()
    except Exception:
        pass

    seconds = round(len(audio) / float(sr), 2) if hasattr(audio, "__len__") else 0
    return {
        "ok": True,
        "file": final.name,
        "seconds": seconds,
        "took_ms": int((time.time() - started) * 1000),
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # 静音默认访问日志
        pass

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send(200, {"ok": True, "model": MODEL, "loaded": _vc is not None, "device": str(getattr(_config, "device", "?"))})
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
            if len(text) > 200:
                self._send(400, {"ok": False, "error": "太长（上限 200 字）"})
                return
            result = synthesize(
                text,
                pitch=int(data.get("pitch") or 0),
                index_rate=float(data.get("index_rate") or 0.3),
            )
            self._send(200, result)
        except Exception as e:
            log(f"error: {e}")
            self._send(500, {"ok": False, "error": str(e)})


def main() -> int:
    log(f"output dir: {OUT_DIR}")
    load_model()  # 预热：启动后第一句就不用等模型加载了
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    log(f"listening http://127.0.0.1:{PORT}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())

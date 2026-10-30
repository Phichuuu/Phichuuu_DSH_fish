# DSH QQ Companion

> 给一个跑在 [DeepSeek Harness](https://www.deepseek.com/) 里的 AI 接上 **QQ**、**嗓子** 和 **一台安卓手机**。
>
> 这一仓库不含桥接本体的代码 —— 它是**胶水**：语音服务、手机适配、健康自愈、记忆同步、备份，
> 以及为此踩过的坑。

---

## 它能让 AI 干嘛

| 能力 | 怎么做到的 |
|---|---|
| **在 QQ 上聊天** | 桥接（第三方）+ 本仓库的预设/工具闸 |
| **会说话、会唱歌** | MiniMax TTS（主）→ MiMo TTS（备）→ 本地 RVC（兜底） |
| **会看图** | DSH 的 `deepseek-flash` 支持 image 输入；截图压缩后直接进上下文 |
| **摸得到手机** | MuMu 模拟器 + `phone-mcp` + adb；点击/滑动/中文输入/截图/录屏抽帧 |
| **有自己的时间** | 定时静默唤醒（不打扰、有配额、断电续得上） |
| **知道自己有记忆** | 共享记忆本 + 日记 + 定时备份 |

---

## 架构

```
                       ┌──────────────────────────┐
   QQ 用户 ◄──────────► │  QQ 客户端（SnowLuma 注入）│
                       └────────────┬─────────────┘
                                    │ OneBot v11 (3000/3001)
                       ┌────────────▼─────────────┐
                       │   qq-bridge（第三方）      │  ← 不含在本仓库
                       │   会话 / 唤醒 / 拟人化     │
                       └────────────┬─────────────┘
                                    │ HTTP（随机端口，自动跟随）
                       ┌────────────▼─────────────┐
                       │  DeepSeek Harness 会话     │
                       └───┬────────┬────────┬────┘
                           │        │        │
              ┌────────────▼─┐ ┌────▼─────┐ ┌▼──────────────┐
              │ 语音 MCP      │ │ 手机 MCP │ │ 日记 / B站 MCP │
              │ :8851/8850   │ │ adb      │ │               │
              └──────────────┘ └──────────┘ └───────────────┘
                  MiniMax          MuMu 模拟器
                  MiMo             安卓 15
                  RVC(本地)
```

---

## 这个仓库里有什么

```
scripts/    开机拉起、健康检查、看门狗、端口跟随、记忆同步、备份
voice/      三个 TTS 守护进程 + MCP 封装 + 截图压缩
plugins/    给 QQ 会话用的预设与工具白名单网关
phone/      MuMu + phone-mcp 的接法与补丁（含两个上游 bug 的修法）
roles/      人格卡模板（脱敏）
config/     config.example.json
docs/       架构 / 语音 / 手机 / 她自己的生活 / 踩坑记录
```

**不在本仓库、需要你自己去拿：**

| 组件 | 地址 | 许可 |
|---|---|---|
| qq-bridge | GitHub 搜 `qq-bridge`（你信任的版本） | MIT |
| ai-companion-kit / phone-mcp | https://github.com/pinganbbOvO/ai-companion-kit | MIT |
| SnowLuma | 用于把 OneBot 接到 QQ | 见其仓库 |
| MuMu 模拟器 | https://mumu.163.com | 免费 |

---

## 快速开始

> 假设你用 Windows + DSH 桌面版。下面是**从零到能说话**的最短路径。

### 1. 前置

- Node.js ≥ 18
- Python ≥ 3.11（语音服务用）
- DeepSeek Harness 桌面版
- 一个能连 QQ 的网关（SnowLuma）
- MuMu 模拟器（只有要用手机才装）

### 2. 装桥接

按 qq-bridge 自己的 README 装好，能收到消息、能回消息。
**先跑通"纯聊天"，别一上来就上语音和手机。**

### 3. 配 DSH 的 MCP

把 `voice/` 下的 MCP 服务挂进 DSH 的 `cordis.patch.yml`（示例）：

```yaml
- insert:
    - id: mcp-voice
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: voice
        transport: stdio
        command: 'C:\Program Files\nodejs\node.exe'
        args: ['<repo>\voice\mcp-voice-server.js']
        env:
          VOICE_DAEMON_URL: 'http://127.0.0.1:8848'
```

完整示例见 `docs/架构.md`。

### 4. 起语音服务

```bash
# 小米 MiMo（可选，唱歌用）
python voice/mimo-tts-daemon.py

# MiniMax（推荐，说话用）
python voice/minimax-tts-daemon.py

# 本地 RVC（兜底，需要自备模型）
python voice/rvc-voice-daemon.py
```

Key 放**文件**里，不要写进代码：

```
<某处>/minimax-key.txt
<某处>/mimo-key.txt
```

### 5. 起手机（可选）

见 `docs/手机控制.md`。核心三步：

1. MuMu 装好 → 开 adb → `adb connect 127.0.0.1:16384`
2. 装 **ADBKeyboard**（否则中文打不进去）
3. 装 phone-mcp → 应用 `phone/patches/` 里的两个补丁

---

## 关键设计（也是踩过的坑）

### 语音：为什么是三级回退

```
MiniMax（真人音色，自然）
  ↓ 挂了 / 没 key
MiMo（文字设计音色，支持唱歌）
  ↓ 挂了 / 没 key
本地 RVC（edge-tts 合成 → 换音色）
```

**只看一条链会踩的坑**：RVC 是"换音色"不是"合成"，喂给它的 TTS 越假，出来越假。
详见 `docs/语音链路.md`。

### 手机：为什么用 UI 树 + 截图两条路

- `phone_dump`（uiautomator）→ 文字版界面，适合**按文字点**
- `phone_screenshot` → 图片，适合**自绘界面**（游戏、部分商店）和"看一眼现在什么样"

截图 900×1600 的 PNG 有 1.3–2.5 MB，**必须压缩**，否则一个图片块就能把上下文撑爆。
本仓库的 `voice/shrink-shot.py` 把它压到 60–250 KB。

### 她自己的生活：为什么需要定时器

桥接的自动唤醒只有「有人说话 / 回复检查 / 群冷场」三种。
**私聊里没有"你自己的时间到了"这种东西** —— 角色卡里写再多"你可以自己玩"，没人叫醒也白搭。

`scripts/` 里没有这部分，因为它需要改桥接源码（加一个 `ownLife` 唤醒原因）。
具体改法见 `docs/她自己的生活.md`（附完整代码）。

### 备份：为什么必须有

我们踩过一次：为了让她加载新工具，连续调了几次"重置会话"接口——
**那个接口会把会话状态里的 `activeTopics` / `memberImpressions` 一起删掉**，
她攒了几天的人际印象没了，而且没有备份。

`scripts/backup-bot-state.ps1` 现在每 20 分钟 + 每次开机各存一份，保留 120 份。

---

## 安全

- **不要**把有支付/银行 App 的手机接到这套东西上。用模拟器或备用机。
- 给 AI 的手机工具**默认包含安装/点击能力**，本仓库的 `plugins/qq-tool-restrict.mjs`
  用白名单把不该给的工具挡在外面。
- QQ 有风控。桥接里的发送频率是踩坑调出来的，**别为了"更灵敏"把它调大**。
- 密钥只放本地文件或环境变量，`.gitignore` 已经挡住常见文件名。

---

## 许可

MIT。第三方组件（qq-bridge、ai-companion-kit、SnowLuma、MuMu）各自遵循其原许可，
本仓库只包含自己写的胶水与文档。

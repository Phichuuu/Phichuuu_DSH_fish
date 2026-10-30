# 脚本说明

全部脚本按"**默认布局**"写死了一部分路径，改两个变量就能用在你自己的机器上。

## 默认布局

```
<repo>/                      这个仓库（随便放哪，建议非系统盘）
F:\qq-bridge\                桥接（第三方项目）
F:\feiyu-voice\              语音服务 + key 文件
F:\RVC\                      本地 RVC 兜底（可选）
F:\MuMuPlayer\               MuMu 模拟器（可选）
%USERPROFILE%\.dsh\          DSH 配置与记忆
```

**改哪里**：看每个文件的头部注释，通常第一行就是路径变量。

---

## 启动类

| 脚本 | 作用 |
|---|---|
| `start-bots.cmd` | **总入口**。按顺序拉起：备份 → 语音服务 → QQ → SnowLuma → 端口跟随 → 桥接 → 记忆同步 → 看门狗 |
| `start-*-hidden.vbs` | 每个服务的无窗口启动器（被 `start-bots.cmd` 调用） |
| `follow-dsh-port.cmd` | 每 60 秒探测 DSH 端口，变了就重写配置并重启桥接 |
| `sync-memory-loop.cmd` | 每 20 分钟：跟端口 → 同步记忆 → 备份 |
| `watchdog-loop.cmd` | 每 2 分钟：健康检查 + 缺什么补什么 |

## 健康与备份

| 脚本 | 作用 |
|---|---|
| `check-bot-health.ps1` | 检查 DSH/QQ/SnowLuma/OneBot/桥接/语音，`-Repair` 会自动重启整条链 |
| `backup-bot-state.ps1` | 快照记忆、人格卡、配置、日记；内容没变就跳过；保留 120 份 |

## 其它

| 脚本 | 作用 |
|---|---|
| `sync-dsh-port.ps1` | 探测 DSH 的 web 端口（401 判定），必要时改 `config.json` |
| `sync-shared-memory.py` | 把 QQ 侧和 B站侧的记忆合并成一份，注入人格卡 |

---

## 开机自启怎么配

注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`：

```
DafeiyuBots     = "<repo>\scripts\start-bots.cmd"
DeepSeekHarness = "F:\DSH\DeepSeek Harness.exe"
```

或者把 `start-bots.cmd` 的快捷方式丢进 `shell:startup`。

**不需要管理员权限**，都是当前用户级别。

---

## 注意事项

- **全部隐藏窗口**（VBS `Run(..., 0, False)`），桌面上不会挂一堆黑框。
- 想要日志就去 `boot.log`、`state/health.log`、`state/backup.log`。
- 这些脚本**只管拉起**，不管优雅退出。关机前不用管，下次开机 `start-bots.cmd` 会先检测再启动（幂等）。

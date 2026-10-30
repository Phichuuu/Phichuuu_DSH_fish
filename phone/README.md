# 手机补丁

上游 [phone-mcp](https://github.com/pinganbbOvO/ai-companion-kit) 在**安卓 15 模拟器**上有两个坑，
不打补丁就用不起来。这里放修法，不复制上游代码（避免和上游分叉）。

改的文件只有一个：`packages/phone-mcp/src/phone-mcp.js`

---

## 补丁 1 · uiautomator dump 段错误

见 `01-uiautomator-segfault.md`

**症状**：`phone_dump` 和 `phone_tap_text` 全部失败，报
`adb shell 失败：UI hierchary dumped to: /sdcard/_dsh_ui.xml`
（注意：这其实是**成功信息**，但退出码非 0）

---

## 补丁 2 · 截图太大

见 `02-screenshot-shrink.md`

**症状**：`phone_screenshot` 返回 1.3–2.5 MB 的 base64 图片，上下文直接爆掉。

---

## 打完怎么验证

```bash
# 1. 语法
node --check src/phone-mcp.js

# 2. 截图（应该返回 image/jpeg，几十到几百 KB）
#    在 MCP 客户端里调 phone_screenshot

# 3. UI 树（应该能列出元素）
#    调 phone_dump
```

注意：改完要**重启 MCP 服务进程**（DSH 在启动时 spawn），否则还是老代码。

# 补丁 1 · uiautomator dump 段错误

## 症状

在**安卓 15** 的 MuMu 模拟器上：

```
phone_dump        → Error: adb shell 失败：UI hierchary dumped to: /sdcard/_dsh_ui.xml
phone_tap_text    → Error: 点击失败：adb shell 失败：UI hierchary dumped to: ...
```

看起来像失败，但 `UI hierchary dumped to:` 其实是**成功**的提示。

## 原因

`uiautomator dump` 把文件写完之后，进程会 **segfault**：

```
$ adb shell "uiautomator dump /sdcard/ui.xml; echo EXIT=$?"
UI hierchary dumped to: /sdcard/ui.xml
EXIT=True
Segmentation fault          ← stderr，退出码非 0
```

文件是好的（`ls -l` 能看到 19714 字节，内容完整），
但 adb 看到非零退出码就把它当失败抛出去。

## 修法

把 dump 那一步包进 try —— 成功与否交给后面 `cat` 能不能拿到 XML 来判断。

`src/phone-mcp.js` 里有 **两处**（`phone_dump` 和 `phone_tap_text`），都要改：

```diff
- await shell(`uiautomator dump ${remote}`);
+ // 安卓 15 上 uiautomator 写完文件后会 segfault（退出码非 0），但 dump 是有效的。
+ // 所以这里不能因为退出码就放弃 —— 交给后面 cat 是否拿到 XML 来判断。
+ try { await shell(`uiautomator dump ${remote}`); } catch { /* dump 文件可能已写好 */ }
```

## 为什么不做成"检测到 segfault 就重试"

重试没用，每次都会 segfault。文件已经写好了，重试只是浪费时间。

## 验证

```bash
adb shell "uiautomator dump /sdcard/ui.xml" ; adb shell "wc -c /sdcard/ui.xml"
```

只要 `wc -c` 能报出一个几千到几万的数字，dump 就是好的。

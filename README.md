# iCloud Passwords Auto-Fill

[English](README_EN.md) | 中文

自动检测并填写 iCloud 密码浏览器扩展的 6 位验证码。

## 背景

在 Windows 上使用 iCloud Passwords + Edge 扩展时，每次彻底关闭并重新打开 Edge，扩展重新初始化后需要输入 6 位验证码。这个工具在后台自动完成该过程。

## 原理

### 1. Edge 生命周期检测
**窗口检测**而非进程检测：枚举 `Chrome_WidgetWin_1` 类名的可见窗口，匹配"Edge"标题。避免 Chromium 启动时瞬间出现的子进程误判。

### 2. 非阻塞状态机
`daemon.py` 使用状态机替代阻塞式 sleep：
```
IDLE  ──Edge启动──▶  WAIT_EXTENSION (2s)  ──到时──▶  WAIT_CODE (8s)
  │▲                                                     │
  │└───────────── Edge关闭（任意状态）──────────────────────┘
  │
  └── Edge运行中 + 对话框出现 ──▶ 自发填充（IME 切换 + 自动输入）
```
- 每 0.5–1s 一个 tick（IDLE 时 1s 省 CPU，active 时 0.5s 快速响应）
- IDLE 状态下持续监听验证码对话框，验证码过期后无需重启 Edge
- `last_code` 去重防止重复填充同一验证码
- 对话框 HWND 缓存，命中后跳过 `EnumWindows`

### 3. 快捷键触发（IME 规避）
- 快捷键：**`Alt+I`**（在 `edge://extensions/shortcuts` 中绑定）
- 中文输入法激活时，Windows TSF 会在内核层拦截键盘事件，导致快捷键无法到达浏览器
- 解决：通过 `WM_INPUTLANGCHANGEREQUEST` 消息**切换 Edge 窗口自身的输入语言**为英文，发完快捷键后保持英文直到验证码输入完成再切回
- 这样也顺带防止中文输入法在自动填充时跳出来打断

### 4. 验证码提取
`EnumWindows` → 找 `iCloudPasswordsExtensionHelper.exe` 进程的 `#32770` 对话框 → `EnumChildWindows` 找 `Static` 控件 → 正则 `\d{3}\s+\d{3}` 提取 6 位验证码。基于 Win32 窗口文本读取，无需 OCR。

### 5. 自动输入
`keybd_event`（传统 Win32 API）逐位发送数字虚拟键码，绕过 UIPI（AppContainer 阻止 `SendInput`）。每位数间隔 8ms，配合 Edge PIN 输入框的自动跳转。

### 6. 输入期间锁键盘
`BlockInput(True)` 屏蔽物理键盘防止误触，输入完成后 `BlockInput(False)` 恢复。需管理员权限，普通权限下跳过并提示。

### 7. 性能优化
- **PID 快照**：`CreateToolhelp32Snapshot` 一次性建进程映射表，替代逐窗口 `OpenProcess`
- **回调重排序**：`find_code()` 先判类名/可见性，99%+ 窗口在廉价检查阶段过滤，避免无效进程句柄开销
- **HWND 缓存**：Edge 窗口和验证码对话框各缓存 HWND，命中后跳过 `EnumWindows`
- **动态轮询间隔**：IDLE 时 1s，active 时 0.5s

### 8. 日志
`print()` 输出到终端，自带时间戳。零文件 IO。

## 依赖

- Python 3.11+
- Windows 11（需安装 iCloud for Windows + Edge 扩展）
- iCloud 密码扩展快捷键设为 `Alt+I`
- 零外部依赖（纯 ctypes，无需 pywin32 等）

```bash
pip install -r requirements.txt
```

## 使用

```bash
# 守护模式（推荐）：检测 Edge 启动 → 切换输入法 → 触发扩展 → 自动填充
#                  Edge 运行中验证码过期也会自动检测并填充
python daemon.py

# 手动模式：手动点击扩展图标 → 自动检测 + 填充
python auto_fill_icloud.py
```

## 编译为 exe

```bash
pip install pyinstaller
pyinstaller --onedir --noconsole --uac-admin --name iCloudAutoFill daemon.py
```

产物在 `dist/iCloudAutoFill/`，其中 `iCloudAutoFill.exe` 为主程序入口。

- `--onedir`：单进程（`--onefile` 会因 bootloader 解压产生双进程）
- `--noconsole`：无控制台窗口，静默后台运行
- `--uac-admin`：启动时请求管理员权限（`BlockInput` 锁键盘需要）

## 文件结构

```
├── auto_fill_icloud.py    # 核心：窗口检测 + 验证码提取 + keybd_event 输入 + BlockInput 锁键盘
├── edge_uia.py            # Edge 窗口查找 + 输入法切换 + Alt+I 快捷键发送
├── edge_watcher.py        # Edge 窗口生命周期监控（窗口检测，非进程检测）
├── daemon.py              # 守护进程入口（状态机调度）
├── tools/                 # 诊断/调试工具
├── requirements.txt
├── .gitignore
└── LICENSE
```

## 免责声明

本工具仅供个人学习、研究及自动化辅助使用。使用本工具即表示您同意：

- 本工具与 Apple Inc.、Microsoft Corporation 无关，未获得其认可、授权或官方支持。
- 本工具通过自动化方式操作第三方软件，可能不符合相关软件或服务的使用条款，请用户自行确认并承担相关风险。
- 本工具的键盘模拟及输入锁定功能可能被安全软件误报。
- 本工具仅用于辅助用户完成自身账号的验证码输入，不读取、保存或导出用户密码、Apple ID 凭据或其他敏感信息。
- 用户应确保仅在自己的设备和账号上使用本工具。作者不对因使用本工具导致的账号限制、服务异常、数据损失或其他直接、间接损失承担责任。

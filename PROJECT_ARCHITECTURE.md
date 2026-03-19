# 🛡️ Hardcore Pomodoro (硬核番茄钟) - 项目需求与架构设计文档 V2.0

## 1. 项目愿景 (Project Vision)
本项目旨在开发一款高拓展性、强系统控制力的桌面端专注软件。核心不仅在于传统的番茄钟倒计时，更在于通过**操作系统底层的进程干预**与**网络层面的定时阻断**，打造一个无死角的沉浸式环境。系统采用严格的分层解耦设计，确保未来功能的平滑扩展。

## 2. 核心功能需求 (Core Requirements)

### 2.1 强制专注与防逃逸机制 (Anti-Escape)
* **全局遮罩：** 专注态下全屏、无边框、置顶覆盖所有显示器。
* **违规惩罚：** 自动嗅探焦点，若用户试图切换至非白名单应用，立刻强制将遮挡界面拉回最前端并夺取焦点。

### 2.2 进程级白名单 (Process-Level Whitelist)
* 脱离不可靠的“窗口标题”判断，深入操作系统 API 提取活跃窗口的 PID 与执行文件绝对路径（如 `code.exe`），进行严格的白名单比对。

### 2.3 [新增] 高度自定义能力 (High Customizability)
* **时间自定义：** 支持用户动态设置专注时长（Work Duration）和休息时长（Break Duration）。
* **UI 自定义：** 锁屏/遮罩界面支持加载本地图片作为背景，并允许用户自定义励志标语（Motto）。

### 2.4 [新增] 网络层定时阻断 (Network-Level Scheduled Blocking)
* **绝对时间调度：** 支持设置真实时间段（例如每日 `08:00 - 11:30`）。
* **域名级屏蔽：** 在设定的时间段内，从系统底层切断对特定网站（如 `bilibili.com`）的访问，时间结束后自动恢复。

---

## 3. 架构设计 (Architecture Design)
系统严格遵循三层架构（MVC/MVVM 变体），通过策略模式（Strategy Pattern）与事件总线（Event Bus）实现高内聚低耦合。

### 3.1 表现层 (Presentation Layer - UI)
* **技术栈：** PySide6 (Qt for Python)。
* **职责：** 仅负责界面渲染、动画加载（QSS/毛玻璃）与用户输入交互。**严禁**在此层包含任何底层系统调用。UI 的状态变更必须由逻辑层发出的信号（Signals）驱动。

### 3.2 领域逻辑层 (Domain Layer - Core)
* **状态机 (State Machine)：** 管理 `IDLE`, `FOCUS`, `BREAK` 等核心状态。
* **配置管理器 (Config Manager)：** 读写 JSON/YAML 文件，提供时间参数、UI 资源路径、进程白名单和网络黑名单的数据源。
* **相对计时器 (Timer)：** 管理番茄钟倒计时，广播 Tick 事件。
* **绝对调度器 (Scheduler)：** [新增] 运行于独立线程，监控系统真实时间，触发定时网络阻断事件。
* **看门狗 (Watchdog)：** 专注状态下高频轮询，执行白名单校验策略。

### 3.3 系统服务层 (System Service Layer - OS Interfaces)
* **职责：** 封装所有与操作系统强相关的 API 调用，向上层提供统一抽象接口（Interface）。
* **进程与窗口服务 (`win_process`)：** 获取 HWND、PID、强行置顶、抢夺焦点。
* **网络服务 (`win_network`)：** [新增] 执行网络阻断策略（初期建议采用动态修改 Windows `hosts` 文件配合 `ipconfig /flushdns` 的方案，后期可扩展为 Windows 防火墙出站规则拦截）。

---

## 4. 目录结构树 (Directory Structure)

```text
hardcore_pomodoro/
├── core/
│   ├── __init__.py
│   ├── state_machine.py        # 状态流转控制
│   ├── timer.py                # 番茄倒计时逻辑
│   ├── scheduler.py            # [新增] 真实时间段调度器
│   ├── watchdog.py             # 进程防逃逸监控
│   └── config_manager.py       # [重构] 统一配置读写 (UI配置, 时长, 黑白名单)
│
├── os_services/
│   ├── __init__.py
│   ├── base.py                 # 抽象系统接口 (Abstract Base Classes)
│   ├── win_process.py          # Windows 进程与窗口 API 实现
│   └── win_network.py          # [新增] Windows 网络层拦截实现 (Hosts/Firewall)
│
├── ui/
│   ├── __init__.py
│   ├── main_window.py          # 主控制台 (参数配置, 黑白名单管理)
│   ├── overlay_window.py       # 锁屏/遮罩界面 (动态读取壁纸与标语)
│   └── assets/                 # 默认样式、图标与占位背景图
│
├── data/
│   └── config.json             # 本地配置文件 (由 config_manager 接管)
│
├── main.py                     # 依赖注入与程序入口
└── requirements.txt            
```

---

## 5. 关键技术风险与约束 (Technical Constraints & Risks)

1.  **权限控制 (UAC 提权)：** * 修改 `hosts` 文件或操作防火墙规则**必须**具有 Administrator 管理员权限。程序在 `main.py` 启动入口处需要编写 UAC 提权逻辑，否则网络阻断模块将引发 PermissionError。
2.  **线程安全 (Thread Safety)：** * `watchdog` 和 `scheduler` 均运行在后台线程。它们向 PySide6 主 UI 线程发送更新指令时，必须使用 Qt 的 Signal/Slot 机制，绝对不可在子线程中直接调用 UI 组件（会导致程序崩溃）。
3.  **DNS 缓存残留：**
    * 在启用/关闭网络屏蔽时，浏览器可能因为自身的 DNS 缓存导致屏蔽延迟生效或恢复失败。`win_network.py` 需要在修改配置后静默执行刷新 DNS 缓存的系统命令。

---



# 🛡️ Hardcore Pomodoro (Plan A) - 落地开发计划书

## 🎯 项目总览 (Executive Summary)
本项目旨在基于 Python 和 PySide6 开发一款高强度防逃逸的桌面专注软件。系统采用**应用层智能拦截 (Plan A)** 方案，核心特点包括：基于“进程名+路径+签名”的三元组防伪装校验、基于只读内存快照的无锁并发模型、SQLite 强一致性规则存储，以及“DNS+Hosts兜底”的网络阻断策略。

## 🗺️ 开发里程碑划分 (Milestones)

### Phase 1: 基础设施与数据基座 (Data Layer & Models)
**目标：** 彻底抛弃脆弱的 JSON，建立稳健的 SQLite 规则仓库，并定义清晰的数据模型。

* **任务 1.1：定义核心数据结构**
    * 使用 `pydantic` 或 `dataclasses` 定义 `ProcessRule` (三元组：名称、路径、签名要求) 和 `NetworkRule` (域名、时间窗口)。
    * 定义 `Profile` (情景模式) 包含上述规则的集合。
* **任务 1.2：初始化 SQLite 引擎**
    * 引入 `sqlite3` 或轻量级 ORM (如 `SQLAlchemy` Core / `Peewee`)。
    * 编写建表脚本 (Tables: `profiles`, `process_rules`, `network_rules`)。
* **任务 1.3：实现 CRUD 数据访问对象 (DAO)**
    * 编写向数据库中增加、删除、修改规则的接口，确保支持数据库事务（Transaction），防止断电导致规则损坏。

### Phase 2: 核心引擎与策略编译层 (Core & Compilation Layer)
**目标：** 解决 UI 线程与后台监控线程的并发冲突，实现“原子级”的规则切换。

* **任务 2.1：实现“策略编译器” (Strategy Compiler)**
    * 编写一个核心类，它的作用是：读取 SQLite 中的当前配置 -> 在内存中生成一个**只读的规则快照 (Read-Only Snapshot)**。
* **任务 2.2：构建状态机 (State Machine)**
    * 实现 `IDLE`, `FOCUS`, `BREAK` 状态流转。
* **任务 2.3：重构 Watchdog 守护线程骨架**
    * 修改后台监控线程，让它**只读取**最新的内存快照，绝不直接碰数据库。
    * 当 UI 层修改了规则并点击“应用”时，生成新快照，通过原子替换（改变快照指针）无缝更新 Watchdog 的判定逻辑。

### Phase 3: 进程防伪装模块 (Process Anti-Spoofing)
**目标：** 落地“身份三元组”校验，彻底封死改名作弊的漏洞，并保证极低的 CPU 占用。

* **任务 3.1：精准路径提取**
    * 调用 Windows API 获取前台窗口 HWND -> 提取 PID -> 使用 `psutil.Process(pid).exe()` 获取绝对路径。
* **任务 3.2：数字签名校验 (可选增强)**
    * 集成 `pefile` 或调用 `WinVerifyTrust`，验证提取到的 `.exe` 文件是否拥有预期的官方数字签名。
* **任务 3.3：建立 PID 验证缓存池 (PID Cache Pool)**
    * 实现 LRU Cache (最近最少使用缓存)。对新出现的 PID 进行三元组耗时校验，将结果存入字典；对已校验的 PID 直接 O(1) 放行/拦截。
* **任务 3.4：暴力夺权动作 (Enforce Action)**
    * 实现当判定违规时，强制将被覆盖的番茄钟全屏 UI 置顶 (`SetWindowPos` TOPMOST) 的惩罚逻辑。

### Phase 4: 网络阻断模块 (Network Blocking)
**目标：** 实现基于真实时间段的域名级精准拦截。

* **任务 4.1：时间调度器 (Scheduler)**
    * 编写后台定时任务，每隔一定时间比对系统时钟与 `NetworkRule` 的时间窗口。
* **任务 4.2：DNS 阻断与 Hosts 兜底逻辑**
    * **主策略：** 修改本地网络适配器的 DNS 服务器指向本地空路由（或者使用 Python 脚本在系统层级干预解析）。
    * **兜底策略：** 动态修改 `C:\Windows\System32\drivers\etc\hosts` 文件，注入屏蔽条目。
* **任务 4.3：强制刷新缓存**
    * 在启用/禁用网络规则后，执行 `ipconfig /flushdns` 以及清理浏览器 socket 池的命令。

### Phase 5: 表现层与工程集成 (UI & Vibe Polish)
**目标：** 将所有底层引擎与 PySide6 界面缝合，处理权限与生命周期。

* **任务 5.1：UAC 提权启动**
    * 在 `main.py` 入口处编写逻辑：检测是否拥有 Administrator 权限。如果没有，触发系统 UAC 弹窗要求用户授权重启进程（网络拦截必需）。
* **任务 5.2：PySide6 主界面与表单**
    * 制作情景模式 (Profile) 的下拉切换菜单。
    * 制作增删改查规则的配置表单（直接调用 Phase 1 的 CRUD 接口）。
* **任务 5.3：全屏遮罩 UI**
    * 实现无边框、支持动态背景图、支持显示自定义 Motto 和倒计时的全屏锁屏界面。
* **任务 5.4：系统托盘 (System Tray)**
    * 让程序在后台静默运行，支持最小化到任务栏右下角。

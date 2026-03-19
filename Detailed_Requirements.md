# 🛡️ Hardcore Pomodoro - 详细架构与接口规范 V3.0

## 1. 系统并发与线程模型 (Concurrency Model)
为了保证 UI 的绝对流畅，且底层轮询不阻塞主程序，系统将采用**多线程 + 消息驱动**的架构：
* **Main Thread (主线程):** 运行 PySide6 的事件循环 (Event Loop)。负责渲染 UI、处理点击事件。**所有对 UI 的修改必须在此线程发生。**
* **Watchdog Thread (守护线程):** 专注状态下启动的 Daemon 线程。每隔 0.5 秒调用 OS API 轮询当前前台进程。发现违规时，通过 `PyQtSignal` 向主线程发送异步信号。
* **Scheduler Thread (调度线程):** 后台 Daemon 线程。每隔 30 秒轮询一次系统真实时间，比对网络黑名单配置的时间段，触发网络阻断/恢复的跨层调用。

## 2. 核心数据结构 (Data Structures)
所有持久化状态统一由 `core/config_manager.py` 管理，落地为本地文件 `data/config.json`。数据 Schema 定义如下：

```json
{
  "timing": {
    "work_duration_minutes": 25,
    "break_duration_minutes": 5
  },
  "ui_customization": {
    "background_image_path": "data/assets/bg.jpg",
    "motto": "Stay focused, stay foolish."
  },
  "process_whitelist": [
    "code.exe",
    "pycharm64.exe",
    "chrome.exe"
  ],
  "network_blacklist": [
    {
      "domain": "bilibili.com",
      "start_time": "08:00",
      "end_time": "11:30",
      "is_active": true
    }
  ]
}
```

## 3. 核心领域逻辑 (Core Domain Logic)

### 3.1 状态机 (StateMachine) 定义
位于 `core/state_machine.py`，管理番茄钟的生命周期：
* `INIT` (就绪态): 可修改配置，等待启动。
* `FOCUS` (专注态): 启动 Watchdog 线程，全屏遮罩激活。
* `BREAK` (休息态): Watchdog 挂起，全屏遮罩解除，等待进入下一个 `FOCUS` 或 `INIT`。
* *状态跃迁必须由显式的函数触发，并广播状态变更信号 (StateChangedSignal)。*

## 4. 操作系统服务层契约 (OS Services Contracts)
在 `os_services/base.py` 中定义严格的 Python 抽象基类 (ABC)。不论底层是 Windows 还是其他系统，必须实现以下接口：

### 4.1 进程监控接口 (`IProcessMonitor`)
```python
from abc import ABC, abstractmethod

class IProcessMonitor(ABC):
    @abstractmethod
    def get_foreground_process_name(self) -> str:
        """
        获取当前处于系统最前端（拥有焦点）的进程可执行文件名。
        返回值示例: 'code.exe'
        异常: 抛出 OSInteractError 如果获取句柄失败
        """
        pass
        
    @abstractmethod
    def force_bring_to_front(self, window_title: str) -> bool:
        """将番茄钟遮罩层强行拉回最前端并夺取焦点"""
        pass
```
*Windows 实现细节思路:* 需要用到 `ctypes.windll.user32.GetForegroundWindow()` 获取句柄 (HWND)，然后通过 `GetWindowThreadProcessId` 获取 PID，最后用 `psutil.Process(pid).name()` 拿到精确的进程名。

### 4.2 网络拦截接口 (`INetworkBlocker`)
```python
from abc import ABC, abstractmethod

class INetworkBlocker(ABC):
    @abstractmethod
    def block_domains(self, domains: list[str]) -> bool:
        """执行底层网络阻断"""
        pass

    @abstractmethod
    def unblock_all(self) -> bool:
        """解除所有阻断"""
        pass
```
*Windows 实现细节思路 (Hosts 策略):*
拦截操作需要修改 `C:\Windows\System32\drivers\etc\hosts` 文件。程序应当在写入前插入自定义标记（如 `# --- POMODORO BLOCK ---`），以便于后续的安全回滚和解除阻断。修改完成后，必须静默执行 `os.system("ipconfig /flushdns")` 清除 DNS 缓存。

## 5. UI 层具体技术要求 (UI Specifications)
位于 `ui/overlay_window.py`：
* **窗口属性配置:** ```python
    self.setWindowFlags(
        Qt.WindowType.FramelessWindowHint |    # 无边框
        Qt.WindowType.WindowStaysOnTopHint |   # 永远置顶
        Qt.WindowType.Tool                     # 不在任务栏显示图标
    )
    ```
* **多屏适配:** 程序启动全屏遮罩时，需要遍历 `QGuiApplication.screens()`，如果用户有外接显示器，必须在每个显示器上都实例化一个 `OverlayWindow` 进行物理遮挡。

## 6. 权限与安全机制 (Security & UAC)
* **权限校验:** `main.py` 在初始化阶段，必须首先检测当前是否以管理员权限（Elevated Privileges）运行。
* 如果不具备管理员权限，程序必须提示用户“网络拦截功能不可用”，或者尝试通过调用系统 API 重启自身并申请 UAC 提权。

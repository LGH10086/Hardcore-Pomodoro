# Hardcore Pomodoro

Hardcore Pomodoro 是一款桌面端强制专注工具，基于 PySide6 构建，支持：

- 番茄钟状态机（INIT/FOCUS/BREAK）
- 番茄轮次控制（专注 X 次，休息 X-1 次）
- 多屏全屏遮罩
- 前台进程白名单守护线程
- 按真实时间段执行的网站域名阻断（Windows hosts）
- 本地 JSON 配置持久化

## 技术栈

- Python 3.10+
- PySide6
- psutil

## 目录结构

```text
Hardcore-Pomodoro/
├── core/
│   ├── config_manager.py
│   ├── scheduler.py
│   ├── state_machine.py
│   ├── timer.py
│   └── watchdog.py
├── os_services/
│   ├── base.py
│   ├── win_network.py
│   └── win_process.py
├── ui/
│   ├── main_window.py
│   └── overlay_window.py
├── data/
│   └── config.json
├── main.py
└── requirements.txt
```

## 快速开始

1. 激活 conda 环境

```powershell
conda activate pomodoro
```

2. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

3. 启动程序

```powershell
python main.py
```

## 权限说明

- 网络阻断需要管理员权限（写入 hosts）。
- 程序启动时会自动尝试 UAC 提权重启（一次点击确认即可）。
- 如未授权管理员权限，主界面会提示网络阻断不可用，但番茄钟、遮罩和看门狗仍可工作。

## 配置说明

默认配置文件是 data/config.json，关键字段如下：

- timing: 专注与休息时长（分钟）
- ui_customization: 背景图路径与标语
- process_whitelist: 允许切换的前台进程名
- network_blacklist: 域名时间段阻断规则

network_blacklist 每一项示例：

```json
{
	"domain": "bilibili.com",
	"start_time": "08:00",
	"end_time": "11:30",
	"is_active": true
}
```

## 当前实现边界

- 目前网络阻断采用 hosts 策略，后续可扩展到 Windows 防火墙策略。
- UAC 提权目前采用运行时能力检测+降级提示，尚未实现自动拉起提权重启。

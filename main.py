from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from core.config_manager import ConfigManager
from core.rule_store import RuleStore
from core.scheduler import SchedulerService
from core.state_machine import StateMachine
from core.strategy_compiler import StrategyCompiler
from core.strategy_runtime import StrategyRuntime
from core.timer import PomodoroTimer
from core.watchdog import WatchdogService
from os_services.base import INetworkBlocker
from os_services.hybrid_network import HybridNetworkBlocker
from os_services.win_dns import WindowsDnsNetworkBlocker
from os_services.win_network import WindowsHostsNetworkBlocker
from os_services.win_process import WindowsProcessMonitor
from ui.main_window import MainWindow


class NoOpNetworkBlocker(INetworkBlocker):
    """Fallback blocker used when app has no admin permission."""

    def block_domains(self, domains: list[str]) -> bool:
        return False

    def unblock_all(self) -> bool:
        return False


def is_running_as_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """Try restarting current script with UAC elevation prompt."""
    script_path = Path(__file__).resolve()
    params = subprocess.list2cmdline([str(script_path), *sys.argv[1:]])
    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            params,
            None,
            1,
        )
        return result > 32
    except Exception:
        return False


def main() -> int:
    if not is_running_as_admin() and "--no-elevate" not in sys.argv:
        if relaunch_as_admin():
            return 0

    app = QApplication(sys.argv)

    workspace = Path(__file__).resolve().parent
    config_path = workspace / "data" / "config.json"
    rules_db_path = workspace / "data" / "rules.db"

    config_manager = ConfigManager(config_path)
    rule_store = RuleStore(rules_db_path)
    rule_store.bootstrap_from_legacy(
        process_whitelist=config_manager.get_process_whitelist(),
        network_blacklist=config_manager.get_network_blacklist(),
    )
    strategy_runtime = StrategyRuntime(StrategyCompiler(rule_store))
    state_machine = StateMachine()
    timer = PomodoroTimer()

    process_monitor = WindowsProcessMonitor()

    is_admin = is_running_as_admin()
    network_blocker: INetworkBlocker
    if is_admin:
        network_blocker = HybridNetworkBlocker(
            dns_blocker=WindowsDnsNetworkBlocker(),
            hosts_blocker=WindowsHostsNetworkBlocker(),
        )
    else:
        network_blocker = NoOpNetworkBlocker()

    watchdog = WatchdogService(
        process_monitor=process_monitor,
        snapshot_provider=strategy_runtime.get_snapshot,
    )
    scheduler = SchedulerService(
        snapshot_provider=strategy_runtime.get_snapshot,
        network_blocker=network_blocker,
    )

    window = MainWindow(
        config_manager=config_manager,
        state_machine=state_machine,
        timer=timer,
        watchdog=watchdog,
        scheduler=scheduler,
        process_monitor=process_monitor,
        rule_store=rule_store,
        strategy_runtime=strategy_runtime,
        is_admin=is_admin,
    )
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

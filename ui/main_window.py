from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from core.models import NetworkRule, ProcessRule
from core.rule_store import RuleStore
from core.scheduler import SchedulerService
from core.state_machine import PomodoroState, StateMachine
from core.strategy_runtime import StrategyRuntime
from core.timer import PomodoroTimer
from core.watchdog import WatchdogService
from os_services.base import IProcessMonitor, OSInteractError
from ui.overlay_window import OverlayWindow


class MainWindow(QMainWindow):
    def __init__(
        self,
        config_manager: ConfigManager,
        state_machine: StateMachine,
        timer: PomodoroTimer,
        watchdog: WatchdogService,
        scheduler: SchedulerService,
        process_monitor: IProcessMonitor,
        rule_store: RuleStore,
        strategy_runtime: StrategyRuntime,
        is_admin: bool,
    ) -> None:
        super().__init__()
        self._config_manager = config_manager
        self._state_machine = state_machine
        self._timer = timer
        self._watchdog = watchdog
        self._scheduler = scheduler
        self._process_monitor = process_monitor
        self._rule_store = rule_store
        self._strategy_runtime = strategy_runtime
        self._is_admin = is_admin
        self._overlays: list[OverlayWindow] = []
        self._target_focus_rounds = 1
        self._current_focus_round = 0
        self._section_sidebar: QListWidget
        self._section_stack: QStackedWidget
        self._section_transition: QPropertyAnimation | None = None
        self._self_process_names = {"python.exe", "pythonw.exe", Path(sys.executable).name.lower()}

        self.setWindowTitle("Hardcore Pomodoro")
        self.resize(1160, 780)

        self._build_ui()
        self._connect_signals()
        self._load_config_into_form()
        self._build_overlay_windows()

        self._scheduler.start()
        if not self._is_admin:
            QMessageBox.warning(self, "权限提醒", "当前未以管理员权限运行，网络阻断功能不可用。")

    def closeEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        self._watchdog.stop()
        self._scheduler.stop()
        self._hide_overlays()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)

        self._status_label = QLabel("状态: INIT")
        self._countdown_label = QLabel("剩余: 00:00")
        self._round_label = QLabel("轮次: 0/0")
        self._admin_label = QLabel("管理员权限: 已开启" if self._is_admin else "管理员权限: 未开启")

        self._work_spin = QSpinBox()
        self._work_spin.setRange(1, 240)
        self._break_spin = QSpinBox()
        self._break_spin.setRange(1, 120)
        self._rounds_spin = QSpinBox()
        self._rounds_spin.setRange(1, 20)

        self._bg_path_edit = QLineEdit()
        self._motto_edit = QLineEdit()

        self._process_table = QTableWidget(0, 4)
        self._process_table.setHorizontalHeaderLabels(["进程名", "绝对路径(可选)", "要求签名", "启用"])
        self._process_table.horizontalHeader().setStretchLastSection(True)
        self._process_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._process_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self._network_table = QTableWidget(0, 4)
        self._network_table.setHorizontalHeaderLabels(["域名", "开始时间", "结束时间", "启用"])
        self._network_table.horizontalHeader().setStretchLastSection(True)
        self._network_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._network_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self._process_name_input = QLineEdit()
        self._process_name_input.setPlaceholderText("例如 code.exe")
        self._process_path_input = QLineEdit()
        self._process_path_input.setPlaceholderText("可选，例如 C:/Program Files/Microsoft VS Code/Code.exe")
        self._process_signature_combo = QComboBox()
        self._process_signature_combo.addItems(["否", "是"])
        self._process_active_combo = QComboBox()
        self._process_active_combo.addItems(["是", "否"])

        self._network_domain_input = QLineEdit()
        self._network_domain_input.setPlaceholderText("例如 bilibili.com")
        self._network_start_input = QLineEdit()
        self._network_start_input.setPlaceholderText("08:00")
        self._network_end_input = QLineEdit()
        self._network_end_input.setPlaceholderText("11:30")
        self._network_active_combo = QComboBox()
        self._network_active_combo.addItems(["是", "否"])

        shell_layout = QHBoxLayout(root)
        shell_layout.setContentsMargins(18, 18, 18, 18)
        shell_layout.setSpacing(16)

        self._section_sidebar = QListWidget()
        self._section_sidebar.setObjectName("sidebar")
        self._section_sidebar.setFixedWidth(200)
        for title in ("专注", "锁屏个性化", "黑白名单管理", "运行日志"):
            self._section_sidebar.addItem(QListWidgetItem(title))
        self._section_sidebar.setCurrentRow(0)
        self._section_sidebar.currentRowChanged.connect(self._on_section_changed)

        content_wrap = QWidget()
        content_layout = QVBoxLayout(content_wrap)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)

        title_wrap = QFrame()
        title_wrap.setObjectName("titleWrap")
        title_layout = QVBoxLayout(title_wrap)
        title_layout.setContentsMargins(12, 10, 12, 10)
        app_title = QLabel("Hardcore Pomodoro")
        app_title.setObjectName("appTitle")
        app_subtitle = QLabel("Focus Without Escape | 选择左侧栏目，打造你的专注系统")
        app_subtitle.setObjectName("appSubtitle")
        title_layout.addWidget(app_title)
        title_layout.addWidget(app_subtitle)
        content_layout.addWidget(title_wrap)

        stats_bar = self._build_stats_bar()
        content_layout.addWidget(stats_bar)

        self._section_stack = QStackedWidget()
        self._section_stack.addWidget(self._build_focus_page())
        self._section_stack.addWidget(self._build_personalization_page())
        self._section_stack.addWidget(self._build_lists_page())
        self._section_stack.addWidget(self._build_log_page())
        content_layout.addWidget(self._section_stack)

        shell_layout.addWidget(self._section_sidebar)
        shell_layout.addWidget(content_wrap, 1)

        self._apply_theme()

    def _build_stats_bar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("statsPanel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        layout.addWidget(self._create_stat_card("当前状态", self._status_label))
        layout.addWidget(self._create_stat_card("倒计时", self._countdown_label))
        layout.addWidget(self._create_stat_card("轮次", self._round_label))
        layout.addWidget(self._create_stat_card("权限", self._admin_label))
        return panel

    def _create_stat_card(self, title: str, value_label: QLabel) -> QWidget:
        card = QFrame()
        card.setObjectName("statCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        caption = QLabel(title)
        caption.setObjectName("statTitle")
        value_label.setObjectName("statValue")
        layout.addWidget(caption)
        layout.addWidget(value_label)
        return card

    def _build_focus_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        intro = QLabel("在这里设置番茄时长与轮次，开始一轮硬核专注。")
        intro.setObjectName("sectionIntro")
        layout.addWidget(intro)

        timing_box = QGroupBox("专注参数")
        grid = QGridLayout()
        grid.addWidget(QLabel("专注时长(分钟)"), 0, 0)
        grid.addWidget(self._work_spin, 0, 1)
        grid.addWidget(QLabel("休息时长(分钟)"), 1, 0)
        grid.addWidget(self._break_spin, 1, 1)
        grid.addWidget(QLabel("专注轮数"), 2, 0)
        grid.addWidget(self._rounds_spin, 2, 1)
        timing_box.setLayout(grid)
        layout.addWidget(timing_box)

        action_bar = QHBoxLayout()
        start_btn = QPushButton("开始专注")
        start_btn.setObjectName("btnPrimary")
        start_btn.clicked.connect(self._on_start_focus)
        stop_btn = QPushButton("停止并重置")
        stop_btn.setObjectName("btnWarn")
        stop_btn.clicked.connect(self._on_stop)
        save_btn = QPushButton("保存当前设置")
        save_btn.clicked.connect(self._save_form_to_config)
        action_bar.addWidget(start_btn)
        action_bar.addWidget(stop_btn)
        action_bar.addWidget(save_btn)
        action_bar.addStretch(1)

        action_host = QFrame()
        action_host.setObjectName("actionHost")
        action_host.setLayout(action_bar)
        layout.addWidget(action_host)
        layout.addStretch(1)
        return page

    def _build_personalization_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        intro = QLabel("自定义锁屏背景和标语，打造你的专注仪式感。")
        intro.setObjectName("sectionIntro")
        layout.addWidget(intro)

        box = QGroupBox("锁屏个性化")
        grid = QGridLayout()
        grid.addWidget(QLabel("背景图片路径"), 0, 0)
        grid.addWidget(self._bg_path_edit, 0, 1)
        browse_btn = QPushButton("选择图片")
        browse_btn.clicked.connect(self._on_pick_image)
        grid.addWidget(browse_btn, 0, 2)
        grid.addWidget(QLabel("励志标语"), 1, 0)
        grid.addWidget(self._motto_edit, 1, 1, 1, 2)
        box.setLayout(grid)
        layout.addWidget(box)

        save_btn = QPushButton("保存并应用锁屏样式")
        save_btn.setObjectName("btnPrimary")
        save_btn.clicked.connect(self._save_form_to_config)
        layout.addWidget(save_btn)
        layout.addStretch(1)
        return page

    def _build_lists_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        intro = QLabel("维护允许切换的进程身份规则与定时网络规则（DNS 主策略 + hosts 兜底）。")
        intro.setObjectName("sectionIntro")
        layout.addWidget(intro)

        whitelist_box = QGroupBox("进程白名单")
        wl = QVBoxLayout(whitelist_box)
        wl.addWidget(QLabel("通过表格维护规则，支持一键添加/删除。"))
        wl.addWidget(self._process_table)

        process_add_row = QHBoxLayout()
        process_add_row.addWidget(self._process_name_input, 2)
        process_add_row.addWidget(self._process_path_input, 3)
        process_add_row.addWidget(QLabel("签名"))
        process_add_row.addWidget(self._process_signature_combo)
        process_add_row.addWidget(QLabel("启用"))
        process_add_row.addWidget(self._process_active_combo)

        process_pick_exe_btn = QPushButton("选择应用(.exe)")
        process_pick_exe_btn.clicked.connect(self._on_pick_process_executable)
        process_pick_foreground_btn = QPushButton("抓取当前前台应用")
        process_pick_foreground_btn.clicked.connect(self._on_pick_foreground_process)

        process_add_btn = QPushButton("添加进程规则")
        process_add_btn.clicked.connect(self._on_add_process_rule)
        process_remove_btn = QPushButton("删除选中进程规则")
        process_remove_btn.setObjectName("btnWarn")
        process_remove_btn.clicked.connect(self._on_remove_process_rule)
        process_add_row.addWidget(process_pick_exe_btn)
        process_add_row.addWidget(process_pick_foreground_btn)
        process_add_row.addWidget(process_add_btn)
        process_add_row.addWidget(process_remove_btn)
        wl.addLayout(process_add_row)

        network_box = QGroupBox("网络黑名单计划")
        nl = QVBoxLayout(network_box)
        nl.addWidget(QLabel("按时间段维护域名规则，支持一键添加/删除。"))
        nl.addWidget(self._network_table)

        network_add_row = QHBoxLayout()
        network_add_row.addWidget(self._network_domain_input, 2)
        network_add_row.addWidget(self._network_start_input)
        network_add_row.addWidget(self._network_end_input)
        network_add_row.addWidget(QLabel("启用"))
        network_add_row.addWidget(self._network_active_combo)

        network_add_btn = QPushButton("添加网络规则")
        network_add_btn.clicked.connect(self._on_add_network_rule)
        network_remove_btn = QPushButton("删除选中网络规则")
        network_remove_btn.setObjectName("btnWarn")
        network_remove_btn.clicked.connect(self._on_remove_network_rule)
        network_add_row.addWidget(network_add_btn)
        network_add_row.addWidget(network_remove_btn)
        nl.addLayout(network_add_row)

        layout.addWidget(whitelist_box)
        layout.addWidget(network_box)

        save_btn = QPushButton("保存黑白名单")
        save_btn.clicked.connect(self._save_form_to_config)
        layout.addWidget(save_btn)
        return page

    def _build_log_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        intro = QLabel("查看运行状态、违规检测、网络调度事件。")
        intro.setObjectName("sectionIntro")
        layout.addWidget(intro)

        realtime_box = QGroupBox("实时前台判定")
        realtime_grid = QGridLayout()
        self._rt_state_value = QLabel("-")
        self._rt_name_value = QLabel("-")
        self._rt_path_value = QLabel("-")
        self._rt_rule_value = QLabel("-")
        self._rt_reason_value = QLabel("-")
        self._rt_signature_value = QLabel("-")

        realtime_grid.addWidget(QLabel("判定"), 0, 0)
        realtime_grid.addWidget(self._rt_state_value, 0, 1)
        realtime_grid.addWidget(QLabel("前台进程"), 1, 0)
        realtime_grid.addWidget(self._rt_name_value, 1, 1)
        realtime_grid.addWidget(QLabel("路径"), 2, 0)
        realtime_grid.addWidget(self._rt_path_value, 2, 1)
        realtime_grid.addWidget(QLabel("命中规则"), 3, 0)
        realtime_grid.addWidget(self._rt_rule_value, 3, 1)
        realtime_grid.addWidget(QLabel("原因"), 4, 0)
        realtime_grid.addWidget(self._rt_reason_value, 4, 1)
        realtime_grid.addWidget(QLabel("签名校验"), 5, 0)
        realtime_grid.addWidget(self._rt_signature_value, 5, 1)
        realtime_box.setLayout(realtime_grid)
        layout.addWidget(realtime_box)

        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setPlaceholderText("日志会实时显示在这里...")
        layout.addWidget(self._log_edit)

        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self._log_edit.clear)
        layout.addWidget(clear_btn)
        self._reset_realtime_panel()
        return page

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #121212, stop:0.45 #201a14, stop:1 #111827);
                color: #f3f4f6;
                font-size: 13px;
            }
            QLabel {
                color: #f3f4f6;
            }
            QFrame#titleWrap {
                border: 1px solid rgba(251, 191, 36, 0.28);
                border-radius: 14px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(20, 20, 20, 0.78), stop:1 rgba(30, 41, 59, 0.64));
            }
            QLabel#appTitle {
                font-size: 28px;
                font-family: "Bahnschrift", "Microsoft YaHei UI";
                font-weight: 700;
                letter-spacing: 0.8px;
                color: #fef3c7;
            }
            QLabel#appSubtitle {
                font-size: 13px;
                font-family: "Segoe UI", "Microsoft YaHei UI";
                color: #fdba74;
                font-weight: 500;
            }
            QListWidget#sidebar {
                border: 1px solid rgba(250, 204, 21, 0.34);
                border-radius: 14px;
                background: rgba(10, 10, 10, 0.7);
                padding: 8px;
                outline: none;
            }
            QListWidget#sidebar::item {
                padding: 12px 10px;
                margin: 4px 0;
                border-radius: 10px;
                color: #fde68a;
                font-size: 15px;
                font-weight: 700;
                font-family: "Bahnschrift", "Microsoft YaHei UI";
            }
            QListWidget#sidebar::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(245, 158, 11, 0.92), stop:1 rgba(249, 115, 22, 0.92));
                color: #111827;
            }
            QFrame#statsPanel {
                border: 1px solid rgba(125, 211, 252, 0.32);
                border-radius: 14px;
                background: rgba(2, 6, 23, 0.6);
            }
            QFrame#statCard {
                border: 1px solid rgba(148, 163, 184, 0.32);
                border-radius: 10px;
                background: rgba(15, 23, 42, 0.68);
                min-height: 62px;
            }
            QLabel#statTitle {
                color: #93c5fd;
                font-size: 11px;
                font-family: "Segoe UI", "Microsoft YaHei UI";
            }
            QLabel#statValue {
                color: #f9fafb;
                font-size: 17px;
                font-weight: 700;
                font-family: "Bahnschrift", "Microsoft YaHei UI";
            }
            QLabel#sectionIntro {
                color: #fdba74;
                font-size: 15px;
                font-weight: 600;
                font-family: "Segoe UI", "Microsoft YaHei UI";
            }
            QGroupBox {
                border: 1px solid rgba(148, 163, 184, 0.35);
                border-radius: 12px;
                margin-top: 12px;
                padding: 10px;
                background: rgba(15, 23, 42, 0.55);
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                color: #fcd34d;
            }
            QLineEdit, QTextEdit, QSpinBox {
                border: 1px solid rgba(148, 163, 184, 0.45);
                border-radius: 8px;
                background: rgba(15, 23, 42, 0.72);
                color: #f3f4f6;
                padding: 6px;
                selection-background-color: #0ea5e9;
            }
            QTableWidget {
                border: 1px solid rgba(148, 163, 184, 0.45);
                border-radius: 10px;
                background: rgba(15, 23, 42, 0.78);
                gridline-color: rgba(148, 163, 184, 0.24);
                color: #f3f4f6;
            }
            QHeaderView::section {
                background: rgba(2, 6, 23, 0.9);
                color: #fde68a;
                padding: 6px;
                border: 1px solid rgba(148, 163, 184, 0.24);
                font-weight: 700;
            }
            QComboBox {
                border: 1px solid rgba(148, 163, 184, 0.45);
                border-radius: 8px;
                background: rgba(15, 23, 42, 0.72);
                color: #f3f4f6;
                padding: 4px 8px;
            }
            QPushButton {
                border: 1px solid rgba(251, 191, 36, 0.55);
                border-radius: 10px;
                padding: 8px 14px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0ea5e9, stop:1 #f59e0b);
                color: #111827;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #22d3ee, stop:1 #fbbf24);
            }
            QPushButton:pressed {
                background: #f59e0b;
            }
            QPushButton#btnPrimary {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #22d3ee);
            }
            QPushButton#btnWarn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ef4444, stop:1 #f97316);
                color: #fff7ed;
            }
            QFrame#actionHost {
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 12px;
                background: rgba(2, 6, 23, 0.55);
            }
            """
        )

    @Slot(int)
    def _on_section_changed(self, index: int) -> None:
        safe_index = max(0, index)
        if safe_index == self._section_stack.currentIndex():
            return

        self._section_stack.setCurrentIndex(safe_index)
        target_page = self._section_stack.currentWidget()
        if target_page is None:
            return

        effect = QGraphicsOpacityEffect(target_page)
        target_page.setGraphicsEffect(effect)

        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(240)
        animation.setStartValue(0.25)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _cleanup() -> None:
            target_page.setGraphicsEffect(None)

        animation.finished.connect(_cleanup)
        self._section_transition = animation
        animation.start()

    def _connect_signals(self) -> None:
        self._state_machine.state_changed.connect(self._on_state_changed)
        self._timer.tick.connect(self._on_tick)
        self._timer.session_completed.connect(self._on_session_completed)

        self._watchdog.violation_detected.connect(self._on_violation_detected)
        self._watchdog.allowed_foreground_detected.connect(self._on_allowed_foreground_detected)
        self._watchdog.foreground_evaluated.connect(self._on_foreground_evaluated)
        self._watchdog.monitor_error.connect(self._append_log)

        self._scheduler.block_applied.connect(self._on_scheduler_block)
        self._scheduler.unblock_applied.connect(self._on_scheduler_unblock)
        self._scheduler.scheduler_error.connect(self._append_log)
        self._rounds_spin.valueChanged.connect(self._on_rounds_value_changed)

    def _build_overlay_windows(self) -> None:
        self._overlays.clear()
        screens = QGuiApplication.screens()
        for idx, _ in enumerate(screens):
            self._overlays.append(OverlayWindow(screen_index=idx))

    def _load_config_into_form(self) -> None:
        timing = self._config_manager.get_timing()
        ui = self._config_manager.get_ui_customization()
        process_rules = self._rule_store.get_process_rules()
        network_rules = self._rule_store.get_network_rules()

        self._work_spin.setValue(timing["work_duration_minutes"])
        self._break_spin.setValue(timing["break_duration_minutes"])
        self._rounds_spin.setValue(timing.get("focus_rounds", 4))
        self._bg_path_edit.setText(ui["background_image_path"])
        self._motto_edit.setText(ui["motto"])
        self._load_process_table(process_rules)
        self._target_focus_rounds = self._rounds_spin.value()
        self._current_focus_round = 0
        self._update_round_status(reset=True)
        self._load_network_table(network_rules)

    def _save_form_to_config(self) -> None:
        timing = {
            "work_duration_minutes": self._work_spin.value(),
            "break_duration_minutes": self._break_spin.value(),
            "focus_rounds": self._rounds_spin.value(),
        }
        ui_customization = {
            "background_image_path": self._bg_path_edit.text().strip(),
            "motto": self._motto_edit.text().strip(),
        }
        process_rules = self._collect_process_rules()
        network_rules = self._collect_network_rules()

        self._rule_store.replace_process_rules(process_rules)
        self._rule_store.replace_network_rules(network_rules)
        self._strategy_runtime.reload()

        process_whitelist = [rule.name for rule in process_rules if rule.is_active]
        network_blacklist = [
            {
                "domain": rule.domain,
                "start_time": rule.start_time,
                "end_time": rule.end_time,
                "is_active": rule.is_active,
            }
            for rule in network_rules
        ]

        self._config_manager.update(
            timing=timing,
            ui_customization=ui_customization,
            process_whitelist=process_whitelist,
            network_blacklist=network_blacklist,
        )
        self._refresh_overlay_content()
        self._append_log("配置已保存并刷新策略快照")

    @Slot(int)
    def _on_rounds_value_changed(self, value: int) -> None:
        if self._state_machine.state == PomodoroState.INIT:
            self._target_focus_rounds = max(1, value)
            self._update_round_status(reset=True)

    def _collect_process_rules(self) -> list[ProcessRule]:
        rules: list[ProcessRule] = []
        for row in range(self._process_table.rowCount()):
            name_item = self._process_table.item(row, 0)
            path_item = self._process_table.item(row, 1)
            sign_item = self._process_table.item(row, 2)
            active_item = self._process_table.item(row, 3)

            name = (name_item.text() if name_item else "").strip().lower()
            path = (path_item.text() if path_item else "").strip()
            require_sig = self._is_yes(sign_item.text() if sign_item else "否")
            active = self._is_yes(active_item.text() if active_item else "是")
            if not name:
                continue

            rules.append(
                ProcessRule(
                    name=name,
                    path=path,
                    require_signature=require_sig,
                    is_active=active,
                )
            )

        must_have = {rule.name for rule in rules}
        if "python.exe" not in must_have:
            rules.append(ProcessRule(name="python.exe"))
        if "pythonw.exe" not in must_have:
            rules.append(ProcessRule(name="pythonw.exe"))
        return rules

    def _collect_network_rules(self) -> list[NetworkRule]:
        rules: list[NetworkRule] = []
        for row in range(self._network_table.rowCount()):
            domain_item = self._network_table.item(row, 0)
            start_item = self._network_table.item(row, 1)
            end_item = self._network_table.item(row, 2)
            active_item = self._network_table.item(row, 3)

            domain = self._normalize_domain(domain_item.text() if domain_item else "")
            start = (start_item.text() if start_item else "").strip() or "00:00"
            end = (end_item.text() if end_item else "").strip() or "23:59"
            active = self._is_yes(active_item.text() if active_item else "是")
            if not domain:
                continue

            rules.append(
                NetworkRule(
                    domain=domain,
                    start_time=start,
                    end_time=end,
                    is_active=active,
                )
            )
        return rules

    def _load_process_table(self, rules: list[ProcessRule]) -> None:
        self._process_table.setRowCount(0)
        for rule in rules:
            self._append_process_row(rule.name, rule.path, rule.require_signature, rule.is_active)

    def _load_network_table(self, rules: list[NetworkRule]) -> None:
        self._network_table.setRowCount(0)
        for rule in rules:
            self._append_network_row(rule.domain, rule.start_time, rule.end_time, rule.is_active)

    def _append_process_row(self, name: str, path: str, require_signature: bool, is_active: bool) -> None:
        row = self._process_table.rowCount()
        self._process_table.insertRow(row)
        self._process_table.setItem(row, 0, QTableWidgetItem(name))
        self._process_table.setItem(row, 1, QTableWidgetItem(path))
        self._process_table.setItem(row, 2, QTableWidgetItem("是" if require_signature else "否"))
        self._process_table.setItem(row, 3, QTableWidgetItem("是" if is_active else "否"))

    def _append_network_row(self, domain: str, start_time: str, end_time: str, is_active: bool) -> None:
        row = self._network_table.rowCount()
        self._network_table.insertRow(row)
        self._network_table.setItem(row, 0, QTableWidgetItem(domain))
        self._network_table.setItem(row, 1, QTableWidgetItem(start_time))
        self._network_table.setItem(row, 2, QTableWidgetItem(end_time))
        self._network_table.setItem(row, 3, QTableWidgetItem("是" if is_active else "否"))

    @Slot()
    def _on_add_process_rule(self) -> None:
        name = self._process_name_input.text().strip().lower()
        if not name:
            QMessageBox.warning(self, "输入不完整", "请先填写进程名。")
            return

        path = self._process_path_input.text().strip()
        require_signature = self._process_signature_combo.currentText() == "是"
        is_active = self._process_active_combo.currentText() == "是"
        self._append_process_row(name, path, require_signature, is_active)

        self._process_name_input.clear()
        self._process_path_input.clear()
        self._process_signature_combo.setCurrentIndex(0)
        self._process_active_combo.setCurrentIndex(0)

    @Slot()
    def _on_remove_process_rule(self) -> None:
        row = self._process_table.currentRow()
        if row >= 0:
            self._process_table.removeRow(row)

    @Slot()
    def _on_add_network_rule(self) -> None:
        domain = self._normalize_domain(self._network_domain_input.text())
        if not domain:
            QMessageBox.warning(self, "输入不完整", "请先填写域名。")
            return

        start_time = self._network_start_input.text().strip() or "00:00"
        end_time = self._network_end_input.text().strip() or "23:59"
        is_active = self._network_active_combo.currentText() == "是"
        self._append_network_row(domain, start_time, end_time, is_active)

        self._network_domain_input.clear()
        self._network_start_input.clear()
        self._network_end_input.clear()
        self._network_active_combo.setCurrentIndex(0)

    @Slot()
    def _on_remove_network_rule(self) -> None:
        row = self._network_table.currentRow()
        if row >= 0:
            self._network_table.removeRow(row)

    @staticmethod
    def _is_yes(value: str) -> bool:
        return value.strip() in {"是", "1", "true", "True", "yes", "on"}

    @staticmethod
    def _normalize_domain(value: str) -> str:
        domain = str(value or "").strip().lower()
        if not domain:
            return ""
        if "://" in domain:
            domain = domain.split("://", 1)[1]
        domain = domain.split("/", 1)[0]
        domain = domain.split(":", 1)[0]
        if domain.startswith("www."):
            domain = domain[4:]
        return domain.strip(".")

    def _refresh_overlay_content(self) -> None:
        ui = self._config_manager.get_ui_customization()
        motto = ui.get("motto", "")
        bg_path = ui.get("background_image_path", "")
        for overlay in self._overlays:
            overlay.update_content(motto, bg_path)

    @Slot()
    def _on_pick_image(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "选择背景图片",
            str(Path.cwd()),
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        if selected:
            self._bg_path_edit.setText(selected)

    @Slot()
    def _on_pick_process_executable(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "选择应用可执行文件",
            str(Path.cwd()),
            "Applications (*.exe)",
        )
        if not selected:
            return

        exe_path = Path(selected)
        self._process_name_input.setText(exe_path.name.lower())
        self._process_path_input.setText(str(exe_path))

    @Slot()
    def _on_pick_foreground_process(self) -> None:
        try:
            process_info = self._process_monitor.get_foreground_process_info()
        except OSInteractError as exc:
            QMessageBox.warning(self, "抓取失败", f"无法读取当前前台应用: {exc}")
            return

        self._process_name_input.setText(process_info.name.lower())
        self._process_path_input.setText(process_info.exe_path)

    @Slot()
    def _on_start_focus(self) -> None:
        self._save_form_to_config()
        self._target_focus_rounds = max(1, self._rounds_spin.value())
        self._current_focus_round = 1
        self._update_round_status()
        self._state_machine.to_focus()

    @Slot()
    def _on_stop(self) -> None:
        self._timer.stop()
        self._current_focus_round = 0
        self._update_round_status(reset=True)
        self._state_machine.to_init()
        self._append_log("已停止并重置")

    @Slot(str)
    def _on_state_changed(self, state_text: str) -> None:
        self._status_label.setText(f"状态: {state_text}")
        state = PomodoroState(state_text)
        if state == PomodoroState.FOCUS:
            self._hide_overlays()
            self._watchdog.start()
            self._timer.start_focus(self._work_spin.value())
            self._update_round_status()
            self._append_log("进入专注态")
        elif state == PomodoroState.BREAK:
            self._hide_overlays()
            self._watchdog.stop()
            self._timer.start_break(self._break_spin.value())
            self._append_log("进入休息态")
        else:
            self._hide_overlays()
            self._watchdog.stop()
            self._current_focus_round = 0
            self._update_round_status(reset=True)
            self._append_log("进入就绪态")

    @Slot(int, str)
    def _on_tick(self, seconds_left: int, phase: str) -> None:
        mm = seconds_left // 60
        ss = seconds_left % 60
        self._countdown_label.setText(f"剩余: {mm:02d}:{ss:02d} ({phase})")

    @Slot(str)
    def _on_session_completed(self, completed_phase: str) -> None:
        if completed_phase == "FOCUS":
            if self._current_focus_round >= self._target_focus_rounds:
                self._append_log("所有专注轮次完成，自动回到就绪态")
                self._state_machine.to_init()
                return
            self._append_log("专注结束，切换到休息")
            self._state_machine.to_break()
        elif completed_phase == "BREAK":
            self._current_focus_round += 1
            self._append_log(f"休息结束，开始第 {self._current_focus_round} 轮专注")
            self._state_machine.to_focus()

    @Slot(str)
    def _on_violation_detected(self, process_name: str) -> None:
        if self._state_machine.state != PomodoroState.FOCUS:
            return
        self._append_log(f"检测到违规进程: {process_name}，尝试夺回焦点")
        self._show_overlays()
        self._process_monitor.force_bring_to_front(OverlayWindow.WINDOW_TITLE)

    @Slot(str)
    def _on_allowed_foreground_detected(self, process_name: str) -> None:
        if self._state_machine.state != PomodoroState.FOCUS:
            return
        allowed_process = process_name.split("|", 1)[0].strip().lower()
        if any(overlay.isVisible() for overlay in self._overlays) and allowed_process in self._self_process_names:
            self._append_log(f"忽略应用自身前台事件: {process_name}")
            return
        self._append_log(f"已回到白名单进程: {process_name}")
        self._hide_overlays()

    @Slot(list)
    def _on_scheduler_block(self, domains: list) -> None:
        self._append_log(f"网络阻断已应用: {', '.join(domains)}")

    @Slot()
    def _on_scheduler_unblock(self) -> None:
        self._append_log("网络阻断已解除")

    @Slot(str)
    def _append_log(self, message: str) -> None:
        self._log_edit.append(message)

    @Slot(object)
    def _on_foreground_evaluated(self, detail: object) -> None:
        if not isinstance(detail, dict):
            return

        allowed = bool(detail.get("allowed", False))
        self._rt_state_value.setText("放行" if allowed else "拦截")
        self._rt_name_value.setText(str(detail.get("name") or "-"))
        self._rt_path_value.setText(str(detail.get("path") or "-"))
        self._rt_rule_value.setText(str(detail.get("matched_rule") or "-"))
        self._rt_reason_value.setText(str(detail.get("reason") or "-"))

        signature_ok = detail.get("signature_ok")
        require_signature = bool(detail.get("require_signature", False))
        if not require_signature:
            self._rt_signature_value.setText("未要求")
        elif signature_ok is True:
            self._rt_signature_value.setText("通过")
        elif signature_ok is False:
            self._rt_signature_value.setText("不通过")
        else:
            self._rt_signature_value.setText("未知")

    def _reset_realtime_panel(self) -> None:
        self._rt_state_value.setText("-")
        self._rt_name_value.setText("-")
        self._rt_path_value.setText("-")
        self._rt_rule_value.setText("-")
        self._rt_reason_value.setText("-")
        self._rt_signature_value.setText("-")

    def _show_overlays(self) -> None:
        self._refresh_overlay_content()
        for overlay in self._overlays:
            overlay.showFullScreen()
            overlay.raise_()
            overlay.activateWindow()

    def _hide_overlays(self) -> None:
        for overlay in self._overlays:
            overlay.hide()

    def _update_round_status(self, reset: bool = False) -> None:
        if reset:
            self._round_label.setText(f"轮次: 0/{self._target_focus_rounds}")
            return
        self._round_label.setText(f"轮次: {self._current_focus_round}/{self._target_focus_rounds}")

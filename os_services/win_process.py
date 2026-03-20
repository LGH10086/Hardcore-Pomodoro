from __future__ import annotations

import ctypes
from ctypes import wintypes

import psutil

from os_services.base import ForegroundProcessInfo, IProcessMonitor, OSInteractError


class WindowsProcessMonitor(IProcessMonitor):
    """Windows implementation for active process inspection and focus control."""

    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32

    def get_foreground_process_name(self) -> str:
        return self.get_foreground_process_info().name

    def get_foreground_process_info(self) -> ForegroundProcessInfo:
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            raise OSInteractError("Unable to get foreground window handle")

        pid = wintypes.DWORD(0)
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            raise OSInteractError("Unable to resolve process id from active window")

        try:
            process = psutil.Process(pid.value)
            name = process.name().lower()
            exe_path = process.exe()
            return ForegroundProcessInfo(pid=pid.value, name=name, exe_path=exe_path)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            raise OSInteractError(f"Unable to resolve process name for pid {pid.value}: {exc}") from exc

    def force_bring_to_front(self, window_title: str) -> bool:
        hwnd = self._user32.FindWindowW(None, window_title)
        if not hwnd:
            return False

        SW_RESTORE = 9
        self._user32.ShowWindow(hwnd, SW_RESTORE)

        foreground_hwnd = self._user32.GetForegroundWindow()
        current_thread = self._kernel32.GetCurrentThreadId()
        target_thread = self._user32.GetWindowThreadProcessId(foreground_hwnd, None)

        self._user32.AttachThreadInput(current_thread, target_thread, True)
        self._user32.SetForegroundWindow(hwnd)
        self._user32.BringWindowToTop(hwnd)
        self._user32.SetFocus(hwnd)
        self._user32.AttachThreadInput(current_thread, target_thread, False)
        return True

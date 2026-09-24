"""Gestion des fenêtres et processus Windows via ctypes user32 et kernel32."""

from __future__ import annotations
import ctypes
from ctypes import wintypes
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Définition des types ctypes
user32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.OpenDesktopW.restype = wintypes.HANDLE
user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
user32.SetThreadDesktop.restype = wintypes.BOOL

user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL

user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.GetForegroundWindow.restype = wintypes.HWND

user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL

SW_RESTORE = 9
SW_SHOW = 5
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _ensure_desktop_access() -> None:
    """S'assure que le thread a accès au bureau interactif standard Windows."""
    try:
        h_desk = user32.OpenDesktopW("default", 0, False, 0x01FF)
        if h_desk:
            user32.SetThreadDesktop(h_desk)
            user32.CloseDesktop(h_desk)
    except Exception:
        pass


def find_window_for_app(target: str) -> int | None:
    """Recherche le HWND d'une fenêtre active correspondant à une application."""
    _ensure_desktop_access()
    target_stem = Path(target).stem.lower()
    is_explorer = target_stem in ("explorer", "cabinetwclass")

    found_hwnd: int | None = None

    def enum_cb(hwnd: int, lparam: int) -> int:
        nonlocal found_hwnd
        if not user32.IsWindowVisible(hwnd):
            return 1

        cls_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls_buf, 256)
        cls_name = cls_buf.value

        if is_explorer:
            # Pour l'Explorateur de fichiers, cibler uniquement les fenêtres de dossiers (CabinetWClass)
            # et ignorer le bureau Windows (Progman, WorkerW) ou la barre des tâches
            if cls_name in ("CabinetWClass", "ExploreWClass"):
                found_hwnd = hwnd
                return 0
            return 1

        # Ignorer les éléments système de l'environnement Windows
        if cls_name in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
            return 1

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0:
            return 1

        h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if h_proc:
            try:
                buf = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(1024)
                if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
                    proc_name = Path(buf.value).stem.lower()
                    if proc_name == target_stem:
                        title_buf = ctypes.create_unicode_buffer(512)
                        user32.GetWindowTextW(hwnd, title_buf, 512)
                        # Conserver la fenêtre si elle a un titre ou une classe applicative connue
                        if title_buf.value or cls_name in ("Chrome_WidgetWin_1", "Framework::CFrame"):
                            found_hwnd = hwnd
                            return 0
            finally:
                kernel32.CloseHandle(h_proc)

        return 1

    try:
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    except Exception as err:
        logger.warning("Erreur lors de l'énumération des fenêtres pour '%s': %s", target, err)

    return found_hwnd


def bring_window_to_foreground(hwnd: int) -> bool:
    """Restaure et place une fenêtre au premier plan en contournant les restrictions de focus de Windows."""
    _ensure_desktop_access()
    if not user32.IsWindow(hwnd):
        return False

    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)

        # Déverrouiller les permissions de mise au premier plan Windows
        try:
            user32.LockSetForegroundWindow(2)  # LSFW_UNLOCK = 2
        except Exception:
            pass

        fore_hwnd = user32.GetForegroundWindow()
        fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, None) if fore_hwnd else 0
        cur_thread = kernel32.GetCurrentThreadId()

        attached = False
        if fore_thread and fore_thread != cur_thread:
            try:
                attached = bool(user32.AttachThreadInput(cur_thread, fore_thread, True))
            except Exception:
                attached = False

        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                try:
                    user32.AttachThreadInput(cur_thread, fore_thread, False)
                except Exception:
                    pass

        # Simulation d'un appui Alt rapide pour contourner la restriction de focus Windows
        user32.keybd_event(0x12, 0, 0, 0)
        user32.keybd_event(0x12, 0, 2, 0)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception as err:
        logger.warning("Échec lors de la mise au premier plan de HWND %d: %s", hwnd, err)
        return False

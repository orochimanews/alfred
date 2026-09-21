"""Gestionnaire d'état applicatif thread-safe pour Alfred."""

from __future__ import annotations
import threading
import time
from typing import Callable, Any
from dataclasses import dataclass, field


@dataclass
class LogEntry:
    """Entrée d'historique d'exécution."""
    timestamp: float = field(default_factory=time.time)
    action_name: str = ""
    trigger_key: str = ""
    mode: str = ""
    status: str = "success"
    details: str = ""

    def formatted_time(self) -> str:
        return time.strftime("%H:%M:%S", time.localtime(self.timestamp))


class StateManager:
    """Centralise l'état dynamique d'Alfred (modes, hooks, logs)."""

    def __init__(self, initial_mode: str = "normal") -> None:
        self._lock = threading.RLock()
        self._current_mode: str = initial_mode
        self._previous_mode: str = initial_mode
        self._is_hook_enabled: bool = True
        self._auto_switched_to_normal: bool = False
        self._observers: list[Callable[[str, Any], None]] = []
        self._logs: list[LogEntry] = []
        self._max_logs: int = 50

    @property
    def current_mode(self) -> str:
        with self._lock:
            return self._current_mode

    @property
    def previous_mode(self) -> str:
        with self._lock:
            return self._previous_mode

    @property
    def is_hook_enabled(self) -> bool:
        with self._lock:
            return self._is_hook_enabled

    @property
    def is_auto_switched_to_normal(self) -> bool:
        """Indique si le mode normal actuel résulte d'une détection automatique de champ texte."""
        with self._lock:
            return self._auto_switched_to_normal and self._current_mode == "normal"

    def set_auto_switched_to_normal(self, value: bool) -> None:
        """Définit si le mode normal a été déclenché par un champ texte (pour retour via Entrée)."""
        with self._lock:
            self._auto_switched_to_normal = bool(value)

    @property
    def logs(self) -> list[LogEntry]:
        with self._lock:
            return list(self._logs)

    def subscribe(self, callback: Callable[[str, Any], None]) -> None:
        """Enregistre un observateur (ex: composant UI). Event signature: (event_type, data)"""
        with self._lock:
            if callback not in self._observers:
                self._observers.append(callback)

    def unsubscribe(self, callback: Callable[[str, Any], None]) -> None:
        """Désenregistre un observateur."""
        with self._lock:
            if callback in self._observers:
                self._observers.remove(callback)

    def _notify(self, event_type: str, data: Any) -> None:
        """Notifie tous les observateurs de manière sécurisée."""
        with self._lock:
            observers = list(self._observers)
        for obs in observers:
            try:
                obs(event_type, data)
            except Exception:
                pass

    def set_mode(self, new_mode: str) -> bool:
        """Change le mode actif."""
        mode_clean = new_mode.strip().lower()
        with self._lock:
            if self._current_mode == mode_clean:
                return False
            self._previous_mode = self._current_mode
            self._current_mode = mode_clean
            if mode_clean != "normal":
                self._auto_switched_to_normal = False

        self._notify("mode_changed", mode_clean)
        return True

    def toggle_mode(self, alternate_mode: str = "normal") -> str:
        """Bascule entre le mode actuel et le mode alternatif (ou le mode précédent)."""
        with self._lock:
            target = alternate_mode if self._current_mode != alternate_mode else self._previous_mode
            if target == self._current_mode:
                target = "normal" if self._current_mode != "normal" else "special"
        self.set_mode(target)
        return target

    def set_hook_enabled(self, enabled: bool) -> None:
        """Active ou suspend l'interception clavier."""
        with self._lock:
            if self._is_hook_enabled == enabled:
                return
            self._is_hook_enabled = enabled

        self._notify("hook_state_changed", enabled)

    def add_log(self, action_name: str, trigger_key: str, mode: str, status: str = "success", details: str = "") -> None:
        """Ajoute une entrée au journal d'activité."""
        entry = LogEntry(
            timestamp=time.time(),
            action_name=action_name,
            trigger_key=trigger_key,
            mode=mode,
            status=status,
            details=details,
        )
        with self._lock:
            self._logs.insert(0, entry)
            if len(self._logs) > self._max_logs:
                self._logs.pop()

        self._notify("log_added", entry)

    def clear_logs(self) -> None:
        """Efface l'historique des actions."""
        with self._lock:
            self._logs.clear()
        self._notify("logs_cleared", None)

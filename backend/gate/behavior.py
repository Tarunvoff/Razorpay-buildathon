"""
Behavioral and session-level anomaly detector for RazorGate.
Maintains a rolling time-window of payment events per agent_id behind a pluggable storage interface.

Computes:
1. Call frequency in rolling window (flags 'high_frequency' if call_count > frequency_threshold).
2. Amount deviation (flags 'amount_deviation' if amount is > N std deviations from the running mean).
"""

from dataclasses import dataclass
import math
import time
from typing import Any, Dict, List, Optional, Protocol, Tuple


class WindowStore(Protocol):
    """Storage interface for rolling window payment events."""

    def get(self, agent_id: str) -> List[Tuple[float, int]]:
        ...

    def append(self, agent_id: str, timestamp: float, amount: int) -> None:
        ...

    def evict(self, agent_id: str, cutoff: float) -> None:
        ...


class InMemoryWindowStore:
    """In-memory reference implementation of WindowStore."""

    def __init__(self) -> None:
        self._store: Dict[str, List[Tuple[float, int]]] = {}

    def get(self, agent_id: str) -> List[Tuple[float, int]]:
        return list(self._store.get(agent_id, []))

    def append(self, agent_id: str, timestamp: float, amount: int) -> None:
        if agent_id not in self._store:
            self._store[agent_id] = []
        self._store[agent_id].append((timestamp, amount))

    def evict(self, agent_id: str, cutoff: float) -> None:
        if agent_id in self._store:
            self._store[agent_id] = [
                (ts, amt) for (ts, amt) in self._store[agent_id] if ts >= cutoff
            ]

    def clear(self) -> None:
        self._store.clear()


class BehaviorAnalyzer:
    """
    Session-level and agent-level behavioral risk detector.
    Evaluates call frequency and amount anomalies over a configurable rolling window.
    """

    def __init__(
        self,
        window_seconds: float = 300.0,
        frequency_threshold: int = 5,
        std_dev_threshold: float = 3.0,
        store: Optional[WindowStore] = None,
    ) -> None:
        self.window_seconds = window_seconds
        self.frequency_threshold = frequency_threshold
        self.std_dev_threshold = std_dev_threshold
        self.store = store if store is not None else InMemoryWindowStore()

    def record_and_evaluate(
        self,
        agent_id: str,
        amount_paise: int,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Records an incoming payment call and calculates behavioral flags.

        Returns:
            Dict containing:
                - flag: bool
                - reasons: list[str] (e.g. ['high_frequency', 'amount_deviation'])
                - session_call_count: int
                - frequency: int
                - amount_deviation_zscore: float
                - window_mean_amount: float
                - window_std_amount: float
        """
        now = timestamp if timestamp is not None else time.time()
        cutoff = now - self.window_seconds

        # 1. Evict events outside rolling window
        self.store.evict(agent_id, cutoff)

        # 2. Append current event and retrieve active window events
        self.store.append(agent_id, now, amount_paise)
        events = self.store.get(agent_id)
        call_count = len(events)

        # 3. Compute amount statistics across window
        amounts = [amt for (_, amt) in events]
        if call_count < 2:
            window_mean = float(amount_paise)
            window_std = 0.0
            z_score = 0.0
        else:
            window_mean = sum(amounts) / call_count
            variance = sum((x - window_mean) ** 2 for x in amounts) / call_count
            window_std = math.sqrt(variance)
            z_score = (
                abs(amount_paise - window_mean) / window_std
                if window_std > 0
                else 0.0
            )

        # 4. Evaluate the two exact flag criteria
        reasons: List[str] = []
        if call_count > self.frequency_threshold:
            reasons.append("high_frequency")
        if call_count >= 2 and z_score > self.std_dev_threshold:
            reasons.append("amount_deviation")

        is_flagged = len(reasons) > 0

        return {
            "flag": is_flagged,
            "reasons": reasons,
            "session_call_count": call_count,
            "frequency": call_count,
            "amount_deviation_zscore": round(z_score, 2),
            "window_mean_amount": round(window_mean, 2),
            "window_std_amount": round(window_std, 2),
        }


# Global default analyzer instance
behavior_analyzer = BehaviorAnalyzer()

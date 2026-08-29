"""
Behavioral and session-level anomaly detector for RazorGate.
Maintains a rolling time-window of payment events per agent_id behind a pluggable storage interface.

CANONICAL THRESHOLD SOURCE:
Default frequency thresholds and window sizes are read directly from policy.yaml
via load_policy_config() to prevent threshold drift across files.
"""

from dataclasses import dataclass
import math
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional, Protocol, Tuple
import yaml

POLICY_CONFIG_PATH = Path(__file__).parent / "policy.yaml"


def _get_default_policy_thresholds() -> tuple[int, float, float]:
    """Reads canonical window and frequency limits from policy.yaml."""
    default_freq = 5
    default_window = 300.0
    default_std_thresh = 3.0
    if POLICY_CONFIG_PATH.exists():
        try:
            with open(POLICY_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                default_freq = int(cfg.get("max_calls_per_agent_per_window", default_freq))
                default_window = float(cfg.get("window_seconds", default_window))
                default_std_thresh = float(cfg.get("amount_deviation_std_threshold", default_std_thresh))
        except Exception:
            pass
    return default_freq, default_window, default_std_thresh


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
        window_seconds: Optional[float] = None,
        frequency_threshold: Optional[int] = None,
        std_dev_threshold: Optional[float] = None,
        store: Optional[WindowStore] = None,
    ) -> None:
        # Load canonical defaults from policy.yaml if not explicitly supplied
        cfg_freq, cfg_window, cfg_std = _get_default_policy_thresholds()
        self.window_seconds = window_seconds if window_seconds is not None else cfg_window
        self.frequency_threshold = frequency_threshold if frequency_threshold is not None else cfg_freq
        self.std_dev_threshold = std_dev_threshold if std_dev_threshold is not None else cfg_std
        self.store = store if store is not None else InMemoryWindowStore()
        self._lock = threading.Lock()

    def record_and_evaluate(
        self,
        agent_id: str,
        amount_paise: int,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Records an incoming payment call and calculates behavioral flags.

        Evaluates two exact flag conditions:
        1. high_frequency: call count in window > frequency_threshold
        2. amount_deviation: amount deviates > std_dev_threshold standard deviations
           from the agent's prior window baseline.

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
        with self._lock:
            now = timestamp if timestamp is not None else time.time()
            cutoff = now - self.window_seconds
    
            # 1. Evict events outside rolling window
            self.store.evict(agent_id, cutoff)
    
            # 2. Retrieve prior window history before appending current call
            prior_events = self.store.get(agent_id)
            prior_amounts = [amt for (_, amt) in prior_events]
            prior_count = len(prior_amounts)
    
            # 3. Compute baseline statistics from prior events
            if prior_count >= 2:
                prior_mean = sum(prior_amounts) / prior_count
                sample_variance = sum((x - prior_mean) ** 2 for x in prior_amounts) / prior_count
                sample_std = math.sqrt(sample_variance)
                # Minimum variance scale floor (5% of mean) to avoid division by zero
                effective_std = max(sample_std, 0.05 * prior_mean if prior_mean > 0 else 1.0)
                z_score = abs(amount_paise - prior_mean) / effective_std
            else:
                prior_mean = float(amount_paise)
                effective_std = 0.0
                z_score = 0.0
    
            # 4. Append current event and retrieve full window state
            self.store.append(agent_id, now, amount_paise)
            all_events = self.store.get(agent_id)
            call_count = len(all_events)
            all_amounts = [amt for (_, amt) in all_events]
            window_mean = sum(all_amounts) / call_count
            window_std = math.sqrt(sum((x - window_mean) ** 2 for x in all_amounts) / call_count)
    
            # 5. Evaluate the two exact flag criteria
            reasons: List[str] = []
            if call_count > self.frequency_threshold:
                reasons.append("high_frequency")
            if prior_count >= 2 and z_score > self.std_dev_threshold:
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

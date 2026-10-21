"""Thread-safe in-memory metrics registry computing honest operational telemetry."""

from __future__ import annotations

import math
import threading
from typing import Any


class SimpleHistogram:
    """Computes summary statistics and percentiles without external heavy dependencies."""

    def __init__(self) -> None:
        self._values: list[float] = []
        self._sum: float = 0.0
        self._count: int = 0
        self._min: float = float("inf")
        self._max: float = float("-inf")

    def observe(self, val: float) -> None:
        """Record an observed measurement."""
        self._values.append(val)
        self._sum += val
        self._count += 1
        if val < self._min:
            self._min = val
        if val > self._max:
            self._max = val

    def percentile(self, p: float) -> float:
        """Compute the p-th percentile (0.0 to 1.0)."""
        if not self._values:
            return 0.0
        sorted_vals = sorted(self._values)
        k = (len(sorted_vals) - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_vals[int(k)]
        d0 = sorted_vals[int(f)] * (c - k)
        d1 = sorted_vals[int(c)] * (k - f)
        return round(d0 + d1, 4)

    def to_dict(self) -> dict[str, Any]:
        """Convert histogram summary to dictionary."""
        return {
            "count": self._count,
            "sum": round(self._sum, 4),
            "min": round(self._min, 4) if self._count > 0 else 0.0,
            "max": round(self._max, 4) if self._count > 0 else 0.0,
            "p50": self.percentile(0.50),
            "p90": self.percentile(0.90),
            "p99": self.percentile(0.99),
        }


class MetricsRegistry:
    """Central metrics collector for AgentOps operational telemetry.

    Provides honest accounting of runs, steps, tools, LLM requests, approvals,
    and sources, with explicit documentation for all approximate metrics.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, dict[tuple[tuple[str, str], ...], float]] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, dict[tuple[tuple[str, str], ...], SimpleHistogram]] = {}

    def _labels_key(self, labels: dict[str, str] | None = None) -> tuple[tuple[str, str], ...]:
        if not labels:
            return ()
        return tuple(sorted(labels.items()))

    def increment_counter(
        self, name: str, value: float = 1.0, labels: dict[str, str] | None = None
    ) -> None:
        """Increment a labeled counter metric."""
        key = self._labels_key(labels)
        with self._lock:
            if name not in self._counters:
                self._counters[name] = {}
            current = self._counters[name].get(key, 0.0)
            self._counters[name][key] = current + value

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge value."""
        with self._lock:
            self._gauges[name] = value

    def adjust_gauge(self, name: str, delta: float) -> None:
        """Adjust a gauge value up or down."""
        with self._lock:
            current = self._gauges.get(name, 0.0)
            self._gauges[name] = max(0.0, current + delta)

    def observe_histogram(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """Observe a value into a histogram."""
        key = self._labels_key(labels)
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = {}
            if key not in self._histograms[name]:
                self._histograms[name][key] = SimpleHistogram()
            self._histograms[name][key].observe(value)

    # High-level domain telemetry recording methods

    def record_run_started(self) -> None:
        """Record initiation of a research run."""
        self.increment_counter("runs_total", 1.0, {"status": "STARTED"})
        self.adjust_gauge("active_runs", 1.0)

    def record_run_completed(self, status: str, duration_seconds: float) -> None:
        """Record completion of a research run."""
        self.increment_counter("runs_total", 1.0, {"status": status})
        self.adjust_gauge("active_runs", -1.0)
        self.observe_histogram("run_duration_seconds", duration_seconds, {"status": status})

    def record_queue_wait(self, wait_seconds: float) -> None:
        """Record queue latency from dispatch to worker pickup."""
        self.observe_histogram("queue_wait_seconds", wait_seconds)

    def record_step_executed(self, tool_name: str, status: str, duration_seconds: float) -> None:
        """Record execution outcome and latency of a plan step."""
        self.increment_counter("steps_total", 1.0, {"tool": tool_name, "status": status})
        self.observe_histogram("step_duration_seconds", duration_seconds, {"tool": tool_name})

    def record_tool_call(self, tool_name: str, status: str, duration_seconds: float) -> None:
        """Record low-level tool invocation metrics."""
        self.increment_counter("tool_calls_total", 1.0, {"tool": tool_name, "status": status})
        self.observe_histogram("tool_duration_seconds", duration_seconds, {"tool": tool_name})

    def record_llm_request(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        duration_seconds: float,
        status: str = "success",
    ) -> None:
        """Record token consumption, estimated pricing, and latency for LLM requests."""
        labels = {"provider": provider, "model": model, "status": status}
        self.increment_counter("llm_requests_total", 1.0, labels)
        self.increment_counter(
            "llm_tokens_total",
            float(prompt_tokens),
            {"provider": provider, "model": model, "type": "prompt"},
        )
        self.increment_counter(
            "llm_tokens_total",
            float(completion_tokens),
            {"provider": provider, "model": model, "type": "completion"},
        )
        self.increment_counter(
            "llm_tokens_total",
            float(prompt_tokens + completion_tokens),
            {"provider": provider, "model": model, "type": "total"},
        )
        self.increment_counter(
            "llm_estimated_cost_usd_total",
            cost_usd,
            {"provider": provider, "model": model},
        )
        self.observe_histogram(
            "llm_duration_seconds", duration_seconds, {"provider": provider, "model": model}
        )

    def record_source_retrieved(self, domain: str, status_code: int | str) -> None:
        """Record empirical source retrieval and HTTP status."""
        self.increment_counter(
            "sources_retrieved_total", 1.0, {"domain": domain, "status": str(status_code)}
        )

    def record_approval_event(self, action: str, verdict: str, wait_seconds: float) -> None:
        """Record human-in-the-loop checkpoint decision and operator response latency."""
        self.increment_counter("approvals_total", 1.0, {"action": action, "verdict": verdict})
        self.observe_histogram("approval_wait_seconds", wait_seconds, {"action": action})

    def record_report_finalized(self, claims_count: int, citations_count: int) -> None:
        """Record synthesis of a final grounded analytical report."""
        self.increment_counter("reports_finalized_total", 1.0)
        self.increment_counter("report_claims_total", float(claims_count))
        self.increment_counter("report_citations_total", float(citations_count))

    def get_summary(self) -> dict[str, Any]:
        """Return a structured JSON metrics summary with honest approximation disclosures."""
        with self._lock:
            # Flatten counters
            counters_out: dict[str, list[dict[str, Any]]] = {}
            for name, labeled_vals in self._counters.items():
                counters_out[name] = [
                    {"labels": dict(lbls), "value": val} for lbls, val in labeled_vals.items()
                ]

            # Gauges
            gauges_out = dict(self._gauges)

            # Histograms
            histograms_out: dict[str, list[dict[str, Any]]] = {}
            for name, labeled_hists in self._histograms.items():
                histograms_out[name] = [
                    {"labels": dict(lbls), "stats": hist.to_dict()}
                    for lbls, hist in labeled_hists.items()
                ]

            return {
                "counters": counters_out,
                "gauges": gauges_out,
                "histograms": histograms_out,
                "approximations": {
                    "llm_estimated_cost_usd_total": (
                        "Approximation based on published vendor per-token pricing matrices. "
                        "Actual cloud provider invoices may vary due to volume tiers, enterprise "
                        "agreements, or prompt caching."
                    ),
                    "queue_wait_seconds": (
                        "Approximation computed via difference between database outbox publication "
                        "timestamp and Celery worker task execution start. Subject to minor host "
                        "clock drift across distributed worker nodes."
                    ),
                    "tool_duration_seconds": (
                        "Includes total wall-clock duration spanning DNS resolution, TLS handshake, "
                        "network transfer, and schema parsing. Does not isolate raw network latency."
                    ),
                },
            }

    def get_prometheus_format(self) -> str:
        """Format metrics into standard Prometheus exposition text."""
        lines: list[str] = [
            "# HELP agentops_active_runs Currently active research runs.",
            "# TYPE agentops_active_runs gauge",
            f"agentops_active_runs {self._gauges.get('active_runs', 0.0)}",
        ]

        with self._lock:
            for name, labeled_vals in self._counters.items():
                prom_name = f"agentops_{name}"
                lines.append(f"# HELP {prom_name} Total count for {name}")
                lines.append(f"# TYPE {prom_name} counter")
                for lbls, val in labeled_vals.items():
                    if lbls:
                        labels_str = ",".join(f'{k}="{v}"' for k, v in lbls)
                        lines.append(f"{prom_name}{{{labels_str}}} {val}")
                    else:
                        lines.append(f"{prom_name} {val}")

            for name, labeled_hists in self._histograms.items():
                prom_name = f"agentops_{name}"
                lines.append(f"# HELP {prom_name} Summary statistics for {name}")
                lines.append(f"# TYPE {prom_name} summary")
                for lbls, hist in labeled_hists.items():
                    stats = hist.to_dict()
                    base_labels = dict(lbls)
                    for q in ("0.5", "0.9", "0.99"):
                        p_val = stats[f"p{int(float(q) * 100)}"]
                        q_labels = {**base_labels, "quantile": q}
                        lbl_str = ",".join(f'{k}="{v}"' for k, v in q_labels.items())
                        lines.append(f"{prom_name}{{{lbl_str}}} {p_val}")
                    lbl_str = ",".join(f'{k}="{v}"' for k, v in base_labels.items())
                    lines.append(f"{prom_name}_sum{{{lbl_str}}} {stats['sum']}")
                    lines.append(f"{prom_name}_count{{{lbl_str}}} {stats['count']}")

        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        """Reset all metrics back to zero (primarily for test isolation)."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


# Global singleton metrics registry
metrics = MetricsRegistry()


def get_metrics() -> MetricsRegistry:
    """Retrieve global MetricsRegistry singleton."""
    return metrics


get_metrics_registry = get_metrics

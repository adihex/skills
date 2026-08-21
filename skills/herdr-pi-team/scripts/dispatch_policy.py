#!/usr/bin/env python3
"""Deterministic bounded-dispatch admission policy."""
from __future__ import annotations

from dataclasses import dataclass


class DispatchRefused(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DispatchPolicy:
    max_active: int = 4
    setup_concurrency: int = 2
    stagger_seconds: float = 1.0
    turn_budget: int = 30
    wall_clock_seconds: float = 1800.0
    memory_pressure_ratio: float = 0.85

    def __post_init__(self):
        if self.max_active < 1 or self.setup_concurrency < 1 or self.setup_concurrency > self.max_active:
            raise ValueError("setup concurrency must be between 1 and max_active")
        if self.turn_budget < 1 or self.wall_clock_seconds <= 0 or self.stagger_seconds < 0:
            raise ValueError("budgets must be positive and stagger cannot be negative")

    def admit(self, *, active_workers: int, setup_workers: int, memory_ratio: float = 0.0) -> dict:
        if active_workers >= self.max_active:
            raise DispatchRefused("MAX_ACTIVE", "active worker limit reached")
        if setup_workers >= self.setup_concurrency:
            raise DispatchRefused("SETUP_BACKPRESSURE", "setup concurrency limit reached")
        if memory_ratio >= self.memory_pressure_ratio:
            raise DispatchRefused("MEMORY_BACKPRESSURE", "memory pressure requires backpressure")
        return {"admitted": True, "max_active": self.max_active, "setup_concurrency": self.setup_concurrency,
                "stagger_seconds": self.stagger_seconds, "turn_budget": self.turn_budget,
                "wall_clock_seconds": self.wall_clock_seconds}

    def launch_plan(self, worker_count: int) -> list[dict]:
        if worker_count < 0:
            raise ValueError("worker_count cannot be negative")
        return [{"ordinal": index, "delay_seconds": round(index * self.stagger_seconds, 3),
                 "turn_budget": self.turn_budget, "wall_clock_seconds": self.wall_clock_seconds}
                for index in range(worker_count)]

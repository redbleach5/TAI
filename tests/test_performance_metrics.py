"""Tests for Performance Metrics."""

import tempfile
import time
from pathlib import Path

import pytest
from src.api.dependencies import get_metrics
from src.infrastructure.services.performance_metrics import (
    PerformanceMetrics,
    StageMetrics,
)


class TestStageMetrics:
    """Tests for StageMetrics."""

    def test_add_sample(self):
        """Should add samples correctly."""
        stage = StageMetrics(name="test")
        stage.add(1.0)
        stage.add(2.0)
        stage.add(3.0)
        assert stage.count == 3
        assert stage.samples == [1.0, 2.0, 3.0]

    def test_max_samples_limit(self):
        """Should respect max_samples limit."""
        stage = StageMetrics(name="test", max_samples=5)
        for i in range(10):
            stage.add(float(i))
        assert stage.count == 5
        assert stage.samples == [5.0, 6.0, 7.0, 8.0, 9.0]

    def test_avg(self):
        """Average should be calculated correctly."""
        stage = StageMetrics(name="test")
        stage.add(1.0)
        stage.add(2.0)
        stage.add(3.0)
        assert stage.avg == 2.0

    def test_med(self):
        """Median should be calculated correctly."""
        stage = StageMetrics(name="test")
        stage.add(1.0)
        stage.add(5.0)
        stage.add(2.0)
        assert stage.med == 2.0

    def test_min_max(self):
        """Min and max should be calculated correctly."""
        stage = StageMetrics(name="test")
        stage.add(3.0)
        stage.add(1.0)
        stage.add(5.0)
        assert stage.min_time == 1.0
        assert stage.max_time == 5.0

    def test_empty_metrics(self):
        """Empty metrics should return 0."""
        stage = StageMetrics(name="test")
        assert stage.count == 0
        assert stage.avg == 0.0
        assert stage.med == 0.0
        assert stage.min_time == 0.0
        assert stage.max_time == 0.0

    def test_to_dict(self):
        """to_dict should return correct format."""
        stage = StageMetrics(name="test")
        stage.add(1.0)
        stage.add(2.0)
        d = stage.to_dict()
        assert d["name"] == "test"
        assert d["count"] == 2
        assert d["avg"] == 1.5
        assert d["median"] == 1.5


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics."""

    def test_record(self):
        """Should record metrics correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = PerformanceMetrics(persist_path=tmpdir)
            metrics.record("stage1", 1.0)
            metrics.record("stage1", 2.0)
            assert metrics._stages["stage1"].count == 2

    def test_get_stats(self):
        """Should return stats for stage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = PerformanceMetrics(persist_path=tmpdir)
            metrics.record("stage1", 1.0)
            stats = metrics.get_stats("stage1")
            assert stats is not None
            assert stats["name"] == "stage1"
            assert stats["count"] == 1

    def test_get_stats_unknown_stage(self):
        """Should return None for unknown stage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = PerformanceMetrics(persist_path=tmpdir)
            assert metrics.get_stats("unknown") is None

    def test_get_all_stats(self):
        """Should return all stats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = PerformanceMetrics(persist_path=tmpdir)
            metrics.record("stage1", 1.0)
            metrics.record("stage2", 2.0)
            all_stats = metrics.get_all_stats()
            assert "stages" in all_stats
            assert "stage1" in all_stats["stages"]
            assert "stage2" in all_stats["stages"]
            assert all_stats["total_samples"] == 2

    def test_estimate_duration_with_data(self):
        """Should use median when enough data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = PerformanceMetrics(persist_path=tmpdir)
            for i in range(5):
                metrics.record("stage1", float(i + 1))
            # samples: 1, 2, 3, 4, 5 -> median = 3
            assert metrics.estimate_duration("stage1") == 3.0

    def test_estimate_duration_default(self):
        """Should use default when not enough data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = PerformanceMetrics(persist_path=tmpdir)
            assert metrics.estimate_duration("unknown", default=10.0) == 10.0

    def test_persistence(self):
        """Metrics should persist to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and record
            metrics1 = PerformanceMetrics(persist_path=tmpdir)
            for _ in range(10):  # Trigger save
                metrics1.record("stage1", 1.0)
            
            # Check file exists
            metrics_file = Path(tmpdir) / "stage_metrics.json"
            assert metrics_file.exists()
            
            # Load in new instance
            metrics2 = PerformanceMetrics(persist_path=tmpdir)
            assert "stage1" in metrics2._stages

    def test_reset(self):
        """Reset should clear all metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = PerformanceMetrics(persist_path=tmpdir)
            for _ in range(10):
                metrics.record("stage1", 1.0)
            metrics.reset()
            assert len(metrics._stages) == 0

    def test_measure_decorator_sync(self):
        """Measure decorator should work for sync functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = PerformanceMetrics(persist_path=tmpdir)
            
            @metrics.measure("test_func")
            def slow_func():
                time.sleep(0.01)
                return "done"
            
            result = slow_func()
            assert result == "done"
            assert "test_func" in metrics._stages
            assert metrics._stages["test_func"].count == 1
            assert metrics._stages["test_func"].samples[0] >= 0.01

    @pytest.mark.asyncio
    async def test_measure_decorator_async(self):
        """Measure decorator should work for async functions."""
        import asyncio
        
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = PerformanceMetrics(persist_path=tmpdir)
            
            @metrics.measure("async_func")
            async def async_slow_func():
                await asyncio.sleep(0.01)
                return "async done"
            
            result = await async_slow_func()
            assert result == "async done"
            assert "async_func" in metrics._stages
            assert metrics._stages["async_func"].count == 1


class TestGetMetrics:
    """Tests for get_metrics from container."""

    def test_get_metrics_returns_instance(self):
        """get_metrics (from dependencies) should return container instance."""
        metrics = get_metrics()
        assert isinstance(metrics, PerformanceMetrics)
        assert get_metrics() is metrics

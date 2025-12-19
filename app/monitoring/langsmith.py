"""
LangSmith tracing integration for observability.
"""

import os
from typing import Optional, Dict, Any, Callable
from functools import wraps
from datetime import datetime
import traceback

from app.config import settings


class LangSmithTracer:
    """LangSmith tracing wrapper."""
    
    def __init__(self):
        self.enabled = False
        self._client = None
        self._initialize()
    
    def _initialize(self):
        """Initialize LangSmith if configured."""
        if settings.LANGSMITH_API_KEY and settings.LANGCHAIN_TRACING_V2:
            try:
                # Set environment variables for LangChain
                os.environ["LANGCHAIN_TRACING_V2"] = "true"
                os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
                os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
                os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
                
                from langsmith import Client
                self._client = Client()
                self.enabled = True
                print(f"✅ LangSmith tracing enabled: {settings.LANGCHAIN_PROJECT}")
            except ImportError:
                print("⚠️ langsmith package not installed. Tracing disabled.")
            except Exception as e:
                print(f"⚠️ LangSmith initialization failed: {e}")
        else:
            print("ℹ️ LangSmith tracing not configured")
    
    def trace_run(
        self,
        name: str,
        run_type: str = "chain",
        inputs: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None
    ):
        """
        Context manager for tracing a run.
        
        Usage:
            with tracer.trace_run("retrieval", inputs={"query": q}):
                # do work
        """
        if not self.enabled:
            return _NoOpContextManager()
        
        try:
            from langsmith import traceable
            return _TracingContextManager(
                client=self._client,
                name=name,
                run_type=run_type,
                inputs=inputs or {},
                metadata=metadata or {}
            )
        except:
            return _NoOpContextManager()
    
    def log_feedback(
        self,
        run_id: str,
        key: str,
        score: float,
        comment: str = None
    ):
        """Log feedback for a run."""
        if self.enabled and self._client:
            try:
                self._client.create_feedback(
                    run_id=run_id,
                    key=key,
                    score=score,
                    comment=comment
                )
            except Exception as e:
                print(f"⚠️ Failed to log feedback: {e}")


class _NoOpContextManager:
    """No-op context manager when tracing is disabled."""
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass
    
    def set_output(self, output):
        pass


class _TracingContextManager:
    """Context manager for tracing runs."""
    
    def __init__(self, client, name, run_type, inputs, metadata):
        self.client = client
        self.name = name
        self.run_type = run_type
        self.inputs = inputs
        self.metadata = metadata
        self.run = None
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.utcnow()
        try:
            self.run = self.client.create_run(
                name=self.name,
                run_type=self.run_type,
                inputs=self.inputs,
                extra={"metadata": self.metadata}
            )
        except Exception as e:
            print(f"⚠️ Failed to create trace run: {e}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.run:
            try:
                if exc_type:
                    self.client.update_run(
                        self.run.id,
                        error=str(exc_val)
                    )
                self.client.update_run(
                    self.run.id,
                    end_time=datetime.utcnow()
                )
            except:
                pass
    
    def set_output(self, output):
        if self.run:
            try:
                self.client.update_run(
                    self.run.id,
                    outputs={"output": output}
                )
            except:
                pass


# Metrics tracking (in-memory + Redis)
class MetricsCollector:
    """Collects and exposes metrics."""
    
    def __init__(self):
        self.metrics = {
            "requests_total": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "escalations": 0,
            "retrieval_failures": 0,
            "llm_failures": 0,
            "avg_confidence": 0.0,
            "confidence_sum": 0.0,
            "confidence_count": 0,
        }
    
    def increment(self, metric: str, value: int = 1):
        """Increment a counter metric."""
        if metric in self.metrics:
            self.metrics[metric] += value
    
    def record_confidence(self, confidence: float):
        """Record confidence score for averaging."""
        self.metrics["confidence_sum"] += confidence
        self.metrics["confidence_count"] += 1
        if self.metrics["confidence_count"] > 0:
            self.metrics["avg_confidence"] = (
                self.metrics["confidence_sum"] / self.metrics["confidence_count"]
            )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics."""
        return {
            **self.metrics,
            "cache_hit_rate": (
                self.metrics["cache_hits"] / 
                (self.metrics["cache_hits"] + self.metrics["cache_misses"])
                if (self.metrics["cache_hits"] + self.metrics["cache_misses"]) > 0
                else 0.0
            )
        }


# Singleton instances
_tracer: Optional[LangSmithTracer] = None
_metrics: Optional[MetricsCollector] = None


def get_tracer() -> LangSmithTracer:
    """Get singleton tracer."""
    global _tracer
    if _tracer is None:
        _tracer = LangSmithTracer()
    return _tracer


def get_metrics() -> MetricsCollector:
    """Get singleton metrics collector."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


def traced(name: str, run_type: str = "chain"):
    """Decorator to trace a function."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.trace_run(name, run_type, inputs={"args": str(args), "kwargs": str(kwargs)}):
                return func(*args, **kwargs)
        return wrapper
    return decorator

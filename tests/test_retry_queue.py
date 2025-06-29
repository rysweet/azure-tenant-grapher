import pytest
import asyncio

from src.resource_processor import ResourceProcessor, ProcessingStats

class DummySessionManager:
    def session(self):
        class DummySession:
            def __enter__(self): return self
            def __exit__(self, exc_type, exc_val, exc_tb): pass
            def run(self, *a, **k): return type("Result", (), {"single": lambda: {"count": 0}})()
        return DummySession()

class TestResourceProcessor(ResourceProcessor):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._call_counts = {}

    async def process_single_resource(self, resource, resource_index):
        rid = resource["id"]
        self._call_counts.setdefault(rid, 0)
        self._call_counts[rid] += 1
        # Simulate: first always succeeds, second fails once then succeeds, third always fails
        if rid == "res1":
            self.stats.successful += 1
            self.stats.processed += 1
            return True
        elif rid == "res2":
            if self._call_counts[rid] == 1:
                self.stats.processed += 1
                return False
            else:
                self.stats.successful += 1
                self.stats.processed += 1
                return True
        elif rid == "res3":
            self.stats.processed += 1
            return False
        else:
            raise Exception("Unknown resource id")

@pytest.mark.asyncio
async def test_retry_and_poison_queue(monkeypatch):
    # Patch logger to silence output
    import logging
    logging.getLogger("src.resource_processor").disabled = True

    resources = [
        {"id": "res1", "name": "Resource 1", "type": "TypeA", "location": "loc", "resource_group": "rg", "subscription_id": "sub"},
        {"id": "res2", "name": "Resource 2", "type": "TypeB", "location": "loc", "resource_group": "rg", "subscription_id": "sub"},
        {"id": "res3", "name": "Resource 3", "type": "TypeC", "location": "loc", "resource_group": "rg", "subscription_id": "sub"},
    ]
    processor = TestResourceProcessor(DummySessionManager(), None, None, max_retries=2)
    # Patch poison_list tracking
    poison_ids = []
    orig_logger_error = processor.__class__.__dict__["process_resources"].__globals__["logger"].error
    def fake_logger_error(msg, *args, **kwargs):
        if msg.startswith("☠️  Poisoned after"):
            # Extract id from message
            parts = msg.split(":")
            if len(parts) > 1:
                poison_ids.append(parts[-1].strip())
        return orig_logger_error(msg, *args, **kwargs)
    monkeypatch.setattr(processor.__class__.__dict__["process_resources"].__globals__["logger"], "error", fake_logger_error)

    stats: ProcessingStats = await processor.process_resources(resources, max_workers=2, progress_callback=None, progress_every=1)
    assert stats.total_resources == 3
    assert stats.successful == 2
    assert stats.failed == 1
    assert set(poison_ids) == {"res3"}
"""Rate-limit storage configuration locks (engineering backlog 2.1).

The limiter's storage must be config-driven: memory:// for dev/tests, shared
Redis in production so all three Gunicorn workers count against one bucket.
Two regressions these tests exist to catch:

- A ``storage_uri`` reappearing in ``extensions.py``'s ``Limiter(...)``
  constructor would silently override ``RATELIMIT_STORAGE_URI`` and
  resurrect the per-worker-counter bug (a 10/min guard becoming ~30/min).
- A config class losing its ``os.environ.get()`` line — the
  MAIL_FROM_ADDRESS gotcha — would leave production silently on memory://.
"""
import importlib
import os
from unittest import mock

import config


class TestConfigPlumbing:
    """RATELIMIT_STORAGE_URI flows env → config classes (reload pattern
    mirrors tests/test_email.py)."""

    def test_base_default_is_memory(self):
        importlib.reload(config)
        assert config.Config.RATELIMIT_STORAGE_URI == 'memory://'

    def test_env_var_reaches_base_config(self):
        with mock.patch.dict(os.environ, {'RATELIMIT_STORAGE_URI': 'redis://elsewhere:6379/0'}):
            importlib.reload(config)
            assert config.Config.RATELIMIT_STORAGE_URI == 'redis://elsewhere:6379/0'
        importlib.reload(config)

    def test_production_defaults_to_local_redis_with_fallback(self):
        importlib.reload(config)
        assert config.ProductionConfig.RATELIMIT_STORAGE_URI == 'redis://localhost:6379/0'
        # Redis outage must degrade to per-worker limiting, never a 500.
        assert config.ProductionConfig.RATELIMIT_IN_MEMORY_FALLBACK_ENABLED is True

    def test_testing_config_pinned_to_memory_despite_env(self):
        with mock.patch.dict(os.environ, {'RATELIMIT_STORAGE_URI': 'redis://elsewhere:6379/0'}):
            importlib.reload(config)
            assert config.TestingConfig.RATELIMIT_STORAGE_URI == 'memory://'
        importlib.reload(config)


class TestLimiterWiring:
    def test_testing_app_uses_memory_storage(self):
        """init_app picks the storage up from config, not a constructor arg."""
        from limits.storage import MemoryStorage

        from app import create_app
        from extensions import limiter

        create_app('testing')
        assert isinstance(limiter.storage, MemoryStorage)

    def test_redis_uri_constructs_redis_storage(self):
        """The pinned redis client satisfies limits' RedisStorage. Construction
        is lazy (no I/O until the first command), so no server is needed."""
        from limits.storage import RedisStorage, storage_from_string

        storage = storage_from_string('redis://localhost:6399/0')
        assert isinstance(storage, RedisStorage)

import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CheckinsConfig(AppConfig):
    name = 'apps.checkins'

    def ready(self):
        # One-line deploy-time diagnosis for the channel layer. Never raises.
        try:
            from django.conf import settings

            layers = getattr(settings, "CHANNEL_LAYERS", {})
            backend = layers.get("default", {}).get("BACKEND", "unknown")
            redis_url = getattr(settings, "REDIS_URL", "")
            if "redis" in backend:
                host = redis_url.split("@")[-1] if redis_url else "(unset)"
                try:
                    import redis as redis_py

                    client = redis_py.Redis.from_url(redis_url, socket_timeout=3)
                    client.ping()
                    logger.warning("CHANNEL_LAYER=redis OK (%s)", host)
                except Exception as exc:
                    logger.error(
                        "REDIS UNREACHABLE (%s): %s — WS live push degraded, "
                        "clients get snapshots + REST polling fallback",
                        host,
                        exc,
                    )
            else:
                logger.warning("CHANNEL_LAYER=%s (single-process only)", backend)
        except Exception:
            logger.exception("channel-layer startup probe failed")

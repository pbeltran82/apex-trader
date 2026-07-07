import time


class MarketDataCache:
    def __init__(self, ttl_seconds=5):
        self.ttl_seconds = ttl_seconds
        self._items = {}

    def get(self, key):
        item = self._items.get(key)

        if not item:
            return None

        value, created_at = item

        if time.time() - created_at > self.ttl_seconds:
            return None

        return value

    def set(self, key, value):
        self._items[key] = (value, time.time())
        return value

    def clear(self):
        self._items.clear()


cache = MarketDataCache()

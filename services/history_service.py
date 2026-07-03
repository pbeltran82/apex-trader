import json
from pathlib import Path


class HistoryService:
    def __init__(self):
        self.log_file = Path("logs/trades.jsonl")

    def get_trades(self):

        if not self.log_file.exists():
            return []

        trades = []

        with open(self.log_file, "r") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                trades.append(json.loads(line))

        return list(reversed(trades))
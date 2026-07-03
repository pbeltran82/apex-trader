import json
from pathlib import Path
from datetime import datetime, timezone


class TradeLogger:
    """
    Writes every trade attempt to a JSON Lines log.

    One JSON object per line keeps the log easy to read
    and easy to import later.
    """

    def __init__(self):
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)

        self.log_file = self.log_dir / "trades.jsonl"

    def log(
        self,
        symbol,
        side,
        qty,
        status,
        reason="",
        order_id=None,
    ):
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol.upper(),
            "side": side.lower(),
            "qty": qty,
            "status": status,
            "reason": reason,
            "order_id": order_id,
        }

        with open(self.log_file, "a") as f:
            f.write(json.dumps(record))
            f.write("\n")
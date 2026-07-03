from math import sqrt


def clean_values(values):
    return [float(v) for v in values if v is not None]


def sma(values, period):
    values = clean_values(values)
    result = []

    for i in range(len(values)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(sum(values[i - period + 1:i + 1]) / period)

    return result


def ema(values, period):
    values = clean_values(values)

    if not values:
        return []

    multiplier = 2 / (period + 1)
    result = [values[0]]

    for price in values[1:]:
        result.append((price - result[-1]) * multiplier + result[-1])

    return result


def rsi(values, period=14):
    values = clean_values(values)

    if len(values) < period + 1:
        return [None] * len(values)

    result = [None] * period
    gains = []
    losses = []

    for i in range(1, len(values)):
        diff = values[i] - values[i - 1]
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        result.append(100)
    else:
        rs = avg_gain / avg_loss
        result.append(100 - (100 / (1 + rs)))

    for i in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

        if avg_loss == 0:
            result.append(100)
        else:
            rs = avg_gain / avg_loss
            result.append(100 - (100 / (1 + rs)))

    return result


def macd(values):
    values = clean_values(values)

    ema12 = ema(values, 12)
    ema26 = ema(values, 26)

    macd_line = [fast - slow for fast, slow in zip(ema12, ema26)]
    signal_line = ema(macd_line, 9)
    histogram = [m - s for m, s in zip(macd_line, signal_line)]

    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    }


def atr(candles, period=14):
    if len(candles) < period:
        return [None] * len(candles)

    true_ranges = []

    for i, candle in enumerate(candles):
        high = float(candle["high"])
        low = float(candle["low"])

        if i == 0:
            true_ranges.append(high - low)
        else:
            prev_close = float(candles[i - 1]["close"])
            true_ranges.append(
                max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close),
                )
            )

    return ema(true_ranges, period)


def bollinger_bands(values, period=20, multiplier=2):
    values = clean_values(values)
    middle = sma(values, period)

    upper = []
    lower = []

    for i in range(len(values)):
        if i < period - 1:
            upper.append(None)
            lower.append(None)
            continue

        window = values[i - period + 1:i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        sd = sqrt(variance)

        upper.append(mean + multiplier * sd)
        lower.append(mean - multiplier * sd)

    return {
        "upper": upper,
        "middle": middle,
        "lower": lower,
    }


def vwap(candles):
    cumulative_price_volume = 0
    cumulative_volume = 0
    result = []

    for candle in candles:
        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])
        volume = float(candle["volume"])

        typical_price = (high + low + close) / 3

        cumulative_price_volume += typical_price * volume
        cumulative_volume += volume

        if cumulative_volume == 0:
            result.append(None)
        else:
            result.append(cumulative_price_volume / cumulative_volume)

    return result


def obv(candles):
    if not candles:
        return []

    result = [0]

    for i in range(1, len(candles)):
        close = float(candles[i]["close"])
        prev_close = float(candles[i - 1]["close"])
        volume = float(candles[i]["volume"])

        if close > prev_close:
            result.append(result[-1] + volume)
        elif close < prev_close:
            result.append(result[-1] - volume)
        else:
            result.append(result[-1])

    return result


def rate_of_change(values, period=12):
    values = clean_values(values)
    result = []

    for i in range(len(values)):
        if i < period:
            result.append(None)
        else:
            previous = values[i - period]
            result.append(((values[i] - previous) / previous) * 100 if previous else 0)

    return result


def volatility(values, period=20):
    values = clean_values(values)

    if len(values) < period:
        return 0

    subset = values[-period:]
    mean = sum(subset) / period
    variance = sum((x - mean) ** 2 for x in subset) / period

    return sqrt(variance)


def support(values, lookback=40):
    values = clean_values(values)
    return min(values[-lookback:]) if values else 0


def resistance(values, lookback=40):
    values = clean_values(values)
    return max(values[-lookback:]) if values else 0


def relative_volume(candles, period=20):
    if len(candles) < period + 1:
        return 1

    current_volume = float(candles[-1]["volume"])
    avg_volume = sum(float(c["volume"]) for c in candles[-period - 1:-1]) / period

    return current_volume / avg_volume if avg_volume else 1


def trend_strength(ema20, ema50, ema200):
    latest20 = ema20[-1]
    latest50 = ema50[-1]
    latest200 = ema200[-1]

    if latest20 > latest50 > latest200:
        return "Strong Bullish"

    if latest20 > latest50:
        return "Bullish"

    if latest20 < latest50 < latest200:
        return "Strong Bearish"

    if latest20 < latest50:
        return "Bearish"

    return "Sideways"


def crossover(fast, slow):
    if len(fast) < 2 or len(slow) < 2:
        return "none"

    if fast[-2] <= slow[-2] and fast[-1] > slow[-1]:
        return "bullish"

    if fast[-2] >= slow[-2] and fast[-1] < slow[-1]:
        return "bearish"

    return "none"


def analyze(candles):
    if len(candles) < 220:
        raise ValueError("Not enough candles for full indicator analysis")

    closes = [float(c["close"]) for c in candles]

    ema9 = ema(closes, 9)
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    ema200 = ema(closes, 200)

    rsi14 = rsi(closes, 14)
    macd_data = macd(closes)
    atr14 = atr(candles, 14)
    bb = bollinger_bands(closes, 20, 2)
    vwap_values = vwap(candles)
    obv_values = obv(candles)
    roc_values = rate_of_change(closes, 12)

    return {
        "last_price": closes[-1],

        "ema9": ema9[-1],
        "ema20": ema20[-1],
        "ema50": ema50[-1],
        "ema200": ema200[-1],

        "rsi": rsi14[-1],

        "macd": macd_data["macd"][-1],
        "signal": macd_data["signal"][-1],
        "histogram": macd_data["histogram"][-1],

        "atr": atr14[-1],

        "bollinger_upper": bb["upper"][-1],
        "bollinger_middle": bb["middle"][-1],
        "bollinger_lower": bb["lower"][-1],

        "vwap": vwap_values[-1],
        "obv": obv_values[-1],
        "roc": roc_values[-1],

        "volatility": volatility(closes, 20),
        "relative_volume": relative_volume(candles, 20),

        "support": support(closes, 40),
        "resistance": resistance(closes, 40),

        "trend": trend_strength(ema20, ema50, ema200),
        "crossover": crossover(ema9, ema20),
    }
TECHNOLOGY = {
    "AAPL", "MSFT", "NVDA", "AMD", "INTC", "QCOM", "TXN",
    "AVGO", "MU", "KLAC", "LRCX", "AMAT", "TSM", "ARM",
    "SMCI", "PLTR", "META", "GOOGL", "NFLX"
}

FINANCIALS = {
    "JPM", "BAC", "GS", "MS", "C", "WFC", "SCHW",
    "AXP", "BLK"
}

HEALTHCARE = {
    "LLY", "UNH", "JNJ", "PFE", "MRK", "ABBV", "TMO"
}

CONSUMER = {
    "AMZN", "HD", "COST", "MCD", "WMT", "TSLA"
}

ENERGY = {
    "XOM", "CVX"
}

INDUSTRIALS = {
    "CAT", "GE", "BA"
}

ETFS = {
    "SPY", "QQQ", "IWM", "DIA"
}


def get_sector(symbol: str) -> str:
    symbol = symbol.upper()

    if symbol in TECHNOLOGY:
        return "Technology"

    if symbol in FINANCIALS:
        return "Financials"

    if symbol in HEALTHCARE:
        return "Healthcare"

    if symbol in CONSUMER:
        return "Consumer"

    if symbol in ENERGY:
        return "Energy"

    if symbol in INDUSTRIALS:
        return "Industrials"

    if symbol in ETFS:
        return "ETF"

    return "Other"
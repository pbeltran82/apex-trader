from backend.portfolio import buy_symbol


class SimulationBroker:

    def buy(self, **kwargs):
        return buy_symbol(**kwargs)

    def sell(self, **kwargs):
        raise NotImplementedError("Sell not implemented yet.")

    def account(self):
        return {}

    def positions(self):
        return []
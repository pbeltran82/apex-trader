from backend.brokers.simulation import SimulationBroker


def get_broker():

    # Future:
    #
    # if settings.BROKER == "alpaca":
    #     return AlpacaBroker()

    return SimulationBroker()
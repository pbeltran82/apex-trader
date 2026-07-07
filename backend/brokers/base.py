from abc import ABC, abstractmethod


class Broker(ABC):

    @abstractmethod
    def buy(self, **kwargs):
        pass

    @abstractmethod
    def sell(self, **kwargs):
        pass

    @abstractmethod
    def account(self):
        pass

    @abstractmethod
    def positions(self):
        pass
import abc

class ExpansionDevice(abc.ABC):
    revision = None
    serial = None
    nports = 0
    
    @abc.abstractmethod
    def detect_eeprom(self, port):
        pass
    
    @abc.abstractmethod
    def reset(self):
        pass

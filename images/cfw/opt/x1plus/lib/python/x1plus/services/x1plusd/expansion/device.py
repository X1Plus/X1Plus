import abc

class ExpansionDevice(abc.ABC):
    revision = None
    serial = None
    nports = 0
    
    # Mapping (string -> string) of /sys/bus/usb/devices port string to
    # marketing label of USB port on an Expander (e.g., "1-1.2" -> "A" for
    # X1P-002).
    usb_port_map = {}
    
    @abc.abstractmethod
    def detect_eeprom(self, port):
        pass
    
    @abc.abstractmethod
    def reset(self):
        pass
    
    def usb_port_id_to_name(self, port):
        for k, v in self.usb_port_map.items():
            if port.startswith(k):
                # just the port name itself?  it's just "port A", then
                if port == k:
                    return v

                # maybe it is something like "1-1.2.3" -- i.e., it's on a
                # hub.  replace the pre-hub part with the marketing label
                # for the port, at least
                return f'{v}.{port.removeprefix(k)}'
        
        # we have no idea what this port is; just give the sysfs name for it
        return port

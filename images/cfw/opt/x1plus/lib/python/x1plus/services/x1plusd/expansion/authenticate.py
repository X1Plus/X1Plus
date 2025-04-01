import logging
import struct

import ecdsa

ECDSA_SIG_LENGTH = 64

X1PLUS_PUBLIC_KEY = """
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAETEug80rktW9jsLMKlEhx7A9Z7jpK
GeOUlEtCSATekDJRyZWQ22y+iGOqs513XqJiHYR0X70eZ4poAeB7c/tgrg==
-----END PUBLIC KEY-----
"""

logger = logging.getLogger(__name__)

def authenticate(eeprom, key=X1PLUS_PUBLIC_KEY):
    if eeprom[-1] == 0xFF:
        logger.error("EEPROM appears to be blank or unsigned")
        return False
    if eeprom[-1] == 1:
        (ser_time, type) = struct.unpack("<LB", eeprom[len(eeprom)-5:])
        logger.error(f"EEPROM has serialization version 1 (time only, unsigned), serialized at {ser_time}")
        return False
    if eeprom[-1] == 2:
        sig = eeprom[len(eeprom)-5-ECDSA_SIG_LENGTH:len(eeprom)-5]
        ser_time_data = eeprom[len(eeprom)-5:]
        
        # knock out the signature and replace with 0xFF
        eeprom = bytearray(eeprom)
        sig_block_size = len(ser_time_data)+ECDSA_SIG_LENGTH
        eeprom[len(eeprom)-sig_block_size:] = b'\xFF' * ECDSA_SIG_LENGTH + ser_time_data
        
        vk = ecdsa.VerifyingKey.from_pem(key)
        
        try:
            if not vk.verify(sig, eeprom):
                logger.error("EEPROM signature type 2 did not verify")
                return False
        except Exception as e:
            logger.error(f"EEPROM signature type 2 verification raised exception: {e}")
            return False
        
        (ser_time, type) = struct.unpack("<LB", eeprom[len(eeprom)-5:])
        logger.debug(f"EEPROM has valid serialization version 2 (signed), serialized at {ser_time}")
        
        return True
    
    logger.error(f"EEPROM has unsupported signature block version {eeprom[-1]}")
    return False

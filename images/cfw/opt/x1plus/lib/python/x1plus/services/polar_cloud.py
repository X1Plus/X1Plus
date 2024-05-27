"""
Module to allow printing using Polar Cloud service.
"""

# from x1plusd.dbus import
from dotenv import load_dotenv

load_dotenv()
PASSWORD = os.getenv("PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")
USER = os.getenv("DB_USER")


class PolarPrint():
    def __init__(self, settings):
        self.polar_settings = settings
        # Don't know if we have dotenv or something similar, so just open the .env
        # file and parse it.
        with open(".env") as env:
            for line in env:
                k, v = line.split("=")
                self.polar_settings[k] = v.strip()
        self.polar_settings.on("polarprint.enabled", lambda: self.sync_startstop())
        self.polar_settings.on("self.pin", lambda: self.set_pin())

    def set_pin(self):
        """Open Polar Cloud interface window and get PIN."""
        pin = self.polar_settings.get("polarprint.pin", None)

        if not pin:


    def set_password(self):
        pw = self.polar_settings.get('ssh.root_password', None)
        if x1plus.utils.is_emulating():
            logger.info(f"EMULATING: would reset password to {pw}")
            return

        if pw is None:
            logger.info(f"falling back on PUSK-based password")
            if os.path.exists('/config/keys/PUSK'):
                pw = base64.encodebytes(open('/config/keys/PUSK', 'rb').read())
            else:
                pw = subprocess.run("/usr/bin/bbl_showpwd 11", shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout
        r = subprocess.run("passwd root", shell=True, input=f"{pw}\n{pw}\n", capture_output = True, text=True)
        logger.info(f"reset password: {r}")


    def set_interface():
        """Get IP and MAC addresses and store them in self.settings."""

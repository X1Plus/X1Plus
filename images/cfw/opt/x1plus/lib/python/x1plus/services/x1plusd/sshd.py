import base64
import os
import subprocess

import x1plus.utils
from .dbus import *

logger = logging.getLogger(__name__)

CONFIG_DIR = "/config/sshd"
HOST_KEYFILE = f"{CONFIG_DIR}/dropbear_ecdsa_host_key"
PIDFILE = "/var/run/x1plus_sshd.pid"

class SSHService():
    def __init__(self, daemon, **kwargs):
        self.daemon = daemon
        self.daemon.settings.on("ssh.enabled", lambda: self.sync_startstop())
        self.daemon.settings.on("ssh.root_password", lambda: self.set_password())
        
        self.sync_startstop()
    
    def sshd_is_running(self):
        return subprocess.run(f"start-stop-daemon -K -q -t -p \"{PIDFILE}\"", shell=True).returncode == 0
    
    def sync_startstop(self):
        enabled = self.daemon.settings.get("ssh.enabled", False)
        running = self.sshd_is_running()
        if enabled and not running:
            self.start_sshd()
        if not enabled and running:
            self.stop_sshd()
    
    def start_sshd(self):
        if not os.path.exists(HOST_KEYFILE):
            logger.info("creating sshd keyfile")
            if not x1plus.utils.is_emulating():
                os.makedirs(CONFIG_DIR, exist_ok=True)
                subprocess.run(f"dropbearkey -t ecdsa -f {HOST_KEYFILE}", shell=True)
        
        self.set_password()
        
        logger.info("starting sshd...")
        rv = subprocess.run(f"start-stop-daemon -S -m -b -p \"{PIDFILE}\" --exec dropbear -- -r \"{HOST_KEYFILE}\" -F -p 22", shell=True).returncode
        if rv != 0:
            logger.error("failed to start sshd!")
    
    def stop_sshd(self):
        logger.info("stopping sshd...")
        rv = subprocess.run(f"start-stop-daemon -K -q -p \"{PIDFILE}\"", shell=True).returncode
        if rv != 0:
            logger.error("failed to stop sshd!")
    
    def set_password(self):
        pw = self.daemon.settings.get('ssh.root_password', None)
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


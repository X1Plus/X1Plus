#!/usr/bin/env python3
import tarfile
from tarfile import TarFile, TarInfo
import sys
import io
import glob
import os

# This sucks.  I wish the packfile support for gensquashfs were less buggy. 
# The glob support is really pretty bad.  But here we are.  We hand-generate
# a tar file, with the files exactly where we want them, that we then feed
# to tar2sqfs.
#
# One silver lining is that it means that we don't have to leave an unpacked
# copy of the Python runtime lying around that can get out of sync and/or
# out of date -- we always pack directly from the prebuilt.  Hooray us, I
# guess!

mtime = os.stat(__file__).st_mtime

bio = io.BytesIO()

tf = TarFile(fileobj = bio, mode = 'w', format = tarfile.GNU_FORMAT)
packed = []

def addfile_once(ti, fileobj = None):
    if ti.name in packed:
        return
    tf.addfile(ti, fileobj)
    packed.append(ti.name)

def dir(dirname):
    ti = TarInfo(dirname)
    ti.type = tarfile.DIRTYPE
    ti.mode = 0o755
    ti.uid = 0
    ti.gid = 0
    ti.mtime = mtime
    addfile_once(ti)

def whiteout(path):
    ti = TarInfo(path)
    ti.type = tarfile.CHRTYPE
    ti.devmajor = 0
    ti.devminor = 0
    ti.mode = 0o0
    ti.uid = 0
    ti.gid = 0
    ti.mtime = mtime
    addfile_once(ti)

def symlink(src, dest):
    ti = TarInfo(src)
    ti.type = tarfile.SYMTYPE
    ti.linkname = dest
    ti.mode = 0o777
    ti.uid = 0
    ti.gid = 0
    ti.mtime = mtime
    addfile_once(ti)

def globfiles(fromdir, todir, eatlinks = []):
    for f in glob.glob('**', root_dir = fromdir, recursive = True):
        if f[-1] == "~":
            continue
        inf = f"{fromdir}/{f}"
        ti = tf.gettarinfo(name = inf)
        if (eatlinks == True or (f in eatlinks)) and ti.type == tarfile.SYMTYPE:
            ti = tf.gettarinfo(name = os.path.join(os.path.dirname(inf), os.readlink(inf)))
        ti.name = f"{todir}/{f}"
        ti.uid = 0
        ti.gid = 0
        ti.uname = "root"
        ti.gname = "root"
        ti.mtime = mtime
        if ti.isfile():
            with open(inf, 'rb') as infd:
                addfile_once(ti, fileobj = infd)
        else:
            addfile_once(ti)

symlink('/root/.ssh', '/config/sshd')
symlink('/etc/localtime', '/usr/share/zoneinfo/Etc/UTC')
symlink('/var/run/utmp', '/dev/null')
symlink('/usr/sbin/mount.smb3', '/usr/sbin/mount.cifs')
symlink('/usr/bin/python', '/opt/python/bin/python3.12')
symlink('/usr/bin/python3', '/opt/python/bin/python3.12')
symlink('/usr/bin/python3-config', '/opt/python/bin/python3.12-config')
symlink('/usr/sbin/x1plus.services.sd_watchdog', '/opt/x1plus/bin/sd_watchdog')

whiteout('/etc/init.d/S50fcgiwrap')
whiteout('/usr/bin/wl')
whiteout('/lib/optee_armtz/380231ac-fb99-47ad-a689-9e017eb6e78a.ta')
whiteout('/lib/optee_armtz/4367fd45-4469-42a6-925d-3857b952704a.ta')
whiteout('/lib/optee_armtz/528938ce-fc59-11e8-8eb2-f2801f1b9fd1.ta')
whiteout('/lib/optee_armtz/5b9e0e40-2636-11e1-ad9e-0002a5d5c51b.ta')
whiteout('/lib/optee_armtz/5ce0c432-0ab0-40e5-a056-782ca0e6aba2.ta')
whiteout('/lib/optee_armtz/614789f2-39c0-4ebf-b235-92b32ac107ed.ta')
whiteout('/lib/optee_armtz/731e279e-aafb-4575-a771-38caa6f0cca6.ta')
whiteout('/lib/optee_armtz/873bcd08-c2c3-11e6-a937-d0bf9c45c61c.ta')
whiteout('/lib/optee_armtz/8cccf200-2450-11e4-abe2-0002a5d5c52c.ta')
whiteout('/lib/optee_armtz/8dddf200-2450-11e4-abe2-0002a5d5c53d.ta')
whiteout('/lib/optee_armtz/a4c04d50-f180-11e8-8eb2-f2801f1b9fd1.ta')
whiteout('/lib/optee_armtz/b3091a65-9751-4784-abf7-0298a7cc35ba.ta')
whiteout('/lib/optee_armtz/c3f6e2c0-3548-11e1-b86c-0800200c9a66.ta')
whiteout('/lib/optee_armtz/d17f73a0-36ef-11e1-984a-0002a5d5c51b.ta')
whiteout('/lib/optee_armtz/dc6b2622-2260-4da6-9f7a-d8d5fa4d2a1e.ta')
whiteout('/lib/optee_armtz/dc6b2623-2260-4da6-9f7a-d8d5fa4d2a1e.ta')
whiteout('/lib/optee_armtz/e13010e0-2ae1-11e5-896a-0002a5d5c51b.ta')
whiteout('/lib/optee_armtz/e626662e-c0e2-485c-b8c8-09fbce6edf3d.ta')
whiteout('/lib/optee_armtz/e6a33ed4-562b-463a-bb7e-ff5e15a493c8.ta')
whiteout('/lib/optee_armtz/f157cda0-550c-11e5-a6fa-0002a5d5c51b.ta')
whiteout('/lib/optee_armtz/ffd2bded-ab7d-4988-95ee-e4962fff7154.ta')

whiteout('/usr/share/ca-certificates/mozilla/DST_Root_CA_X3.crt')
whiteout('/etc/ssl/certs/DST_Root_CA_X3.pem')
whiteout('/etc/ssl/certs/2e5ac55d.0')

globfiles("cfw/etc", "/etc")
globfiles("cfw/usr", "/usr", eatlinks = [ 'bin/jq', 'lib/libvncserver.so.1' ])
globfiles("cfw/lib", "/lib")
globfiles("cfw/sbin", "/sbin")
globfiles("cfw/system", "/system", eatlinks = True)
globfiles("cfw/opt", "/opt", eatlinks = True)
globfiles("site-packages", "/opt/python/lib/python3.12/site-packages")

symlink('/usr/libexec/sftp-server', '/usr/libexec/gesftpserver')

with tarfile.open('../prebuilt/python3.tar.gz', 'r') as itf:
    for ti in itf.getmembers():
        if ti.name[:2] == './':
            ti.name = ti.name[2:]
        if ti.name == '.':
            continue
        ti.name = "/opt/python/" + ti.name
        ti.uname = "root"
        ti.gname = "root"
        ti.uid = 0
        ti.gid = 0
        ti.mtime = mtime
        if ti.isfile():
            addfile_once(ti, itf.extractfile(ti))
        else:
            addfile_once(ti)

tf.close()
sys.stdout.buffer.write(bio.getbuffer())

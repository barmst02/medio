#
# exiftool -r -d DSTDIR/%Y/%m_%b/%Y%m%d_%H%M%S%%c.%%e "-filename<CreateDate" SRCDIR
#

import os, time, sys, traceback
import pyinotify
import ConfigParser
from threading import Timer

PKGDIR="/usr/syno/synoman/webman/3rdparty/Medio"
PHOTO_DIR = '/var/services/photo/'
LOG=os.path.join(PKGDIR, 'medio.log')

def log(msg):
    l = open(LOG, "a")
    l.write('[%s] %s\n' % (time.ctime(), str(msg)))

class Config(object):
    def __init__(self):
        self.cfg = ConfigParser.SafeConfigParser()
        self.cfg.read(os.path.join(PKGDIR, 'cfg.ini'))
    
    @property
    def UI_SRCDIR(self):
        return self.cfg.get('UI', 'UI_SRCDIR')

    @property
    def UI_DSTDIR(self):
        return self.cfg.get('UI', 'UI_DSTDIR')

class Process(object):
    def __init__(self, args, shell=False, env=None):
        handle = subprocess.Popen(args, stdin=open(os.devnull, 'r'), stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, close_fds=True, shell=shell, env=env)
        self.stdout, self.stderr = handle.communicate()
        self.retval = handle.wait()

cfg = Config()

def process_file(path):
    srcdir = os.path.join(PHOTO_DIR, cfg.UI_SRCDIR, path)
    dstdir = os.path.join(PHOTO_DIR, cfg.UI_DSTDIR, r'%Y/%m_%b/%Y%m%d_%H%M%S%%c.%%e')
    cmd = 'exiftool -r -d %s "-filename<CreateDate" %s' % (dstdir, srcdir)
    log("RUN %s" % cmd)

class EventHandler(pyinotify.ProcessEvent):
    def process_IN_CREATE(self, event):
        log("Created: %s" % event.pathname)
        Timer(5, process_file, (event.pathname,)).start()
        
    def process_IN_MOVED_TO(self, event):
        log("Moved in: %s" % event.pathname)
        
    def process_IN_CLOSE_WRITE(self, event):
        log("Wrote: %s" % event.pathname)
        
if __name__ == '__main__':
    try:
        wm = pyinotify.WatchManager()
        mask = pyinotify.IN_CREATE | pyinotify.IN_MOVED_TO 
        notifier = pyinotify.Notifier(wm, EventHandler())
        wdd = wm.add_watch(os.path.join(PHOTO_DIR, cfg.UI_SRCDIR), mask)
        notifier.loop()
    except:
        err = traceback.format_exc(2)
        log(err)


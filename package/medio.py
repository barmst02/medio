#
# exiftool -r -d DSTDIR/%Y/%m_%b/%Y%m%d_%H%M%S%%c.%%e "-filename<CreateDate" SRCDIR
#

import os, time, sys, traceback, subprocess
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
    cmd = [os.path.join(PKGDIR, 'exiftool'), '-r', '-d', dstdir, "-filename<CreateDate", srcdir]
    p = Process(cmd)
    if p.retval == 0:
        log('exiftool succeeded for ' + path + ': ' + ' '.join(p.stdout.split('\n')))
    else:
        log('exiftool FAILED for ' + path + ': ' +  ' '.join(p.stderr.split('\n')))

class EventHandler(pyinotify.ProcessEvent):
    def is_relevant_file(self, path):
        (root, ext) = os.path.splitext(path)
        if ext.lower() in ['.jpg', '.jpeg', '.mpg', '.mp4']:
            return True
        return False
    def process_IN_CREATE(self, event):
        if self.is_relevant_file(event.pathname):
            log("Notified of new file: %s" % event.pathname)
            Timer(15, process_file, (event.pathname,)).start()
        
    def process_IN_CLOSE_WRITE(self, event):
        if self.is_relevant_file(event.pathname):
            log("Notified of file write: %s" % event.pathname)

    def process_IN_MOVED_TO(self, event):
        if self.is_relevant_file(event.pathname):
            log("Notified of file moved in: %s" % event.pathname)
            Timer(5, process_file, (event.pathname,)).start()
        
        
if __name__ == '__main__':
    try:
        wm = pyinotify.WatchManager()
        mask = pyinotify.IN_CREATE | pyinotify.IN_MOVED_TO | pyinotify.IN_CLOSE_WRITE
        notifier = pyinotify.Notifier(wm, EventHandler())
        wdd = wm.add_watch(os.path.join(PHOTO_DIR, cfg.UI_SRCDIR), mask)
        notifier.loop()
    except:
        err = traceback.format_exc(2)
        log(err)


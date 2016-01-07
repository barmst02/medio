#
# Medio: Automatic media organizer for Synology Photo Station
# Copyright(c) 2016 Jonathan Poland
#

import re, os, time, sys, traceback, subprocess
import pyinotify
import ConfigParser
from threading import _Timer

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

class LoggingTimer(_Timer):
    def run(self):
        try:
            _Timer.run(self)
        except:
            err = traceback.format_exc(2)
            log(err)

cfg = Config()

class EventHandler(pyinotify.ProcessEvent):
    active = {}
    reindex_timer = None
    rename_re = re.compile(r"'(\S+)'\s+-->\s+'(\S+)'")

    def __init__(self):
        # Check for files we may have missed and queue events to process them
        for entry in os.listdir(os.path.join(PHOTO_DIR, cfg.UI_SRCDIR)):
            if self.is_relevant_file(entry):
                log(entry)
                LoggingTimer(1, self.process_file, (entry,)).start()
    def reindex(self):
        cmd = ['/usr/syno/bin/synoindex', '-R', os.path.join(PHOTO_DIR, cfg.UI_SRCDIR)]
        p = Process(cmd)
        if p.retval != 0:
            log('synoindex reindex FAILED: ' +  ' '.join(p.stderr.split('\n')))
        log('Reindexing %s...' % os.path.join(PHOTO_DIR, cfg.UI_SRCDIR))
        self.reindex_timer = None

    def process_file(self, path):
        if path in self.active:
            del self.active[path]
        srcfile = os.path.join(PHOTO_DIR, cfg.UI_SRCDIR, path)
        dstfmt = os.path.join(PHOTO_DIR, cfg.UI_DSTDIR, r'%Y/%m_%b/%Y%m%d_%H%M%S%%c.%%e')
        dstfile = None
        # Use exiftool to do the rename
        cmd = [os.path.join(PKGDIR, 'exiftool'), '-v', '-r', '-d', dstfmt, 
                "-filename<filemodifydate", "-filename<createdate", 
                "-filename<datetimeoriginal", srcfile]
        p = Process(cmd)
        if p.retval != 0:
            log('exiftool FAILED for ' + path + ': ' +  ' '.join(p.stderr.split('\n')))
            return
        for line in p.stdout.split('\n'):
            m = self.rename_re.match(line)
            if m and m.group(1) == srcfile:
                dstfile = m.group(2)
                log('Moved %s to %s' % (srcfile, dstfile))
        if dstfile is None:
            log('exiftool succeeded, but no output information found')
            return
        # Tell synology it moved (synoindex)
        cmd = ['/usr/syno/bin/synoindex', '-n', dstfile, srcfile]
        p = Process(cmd)
        if p.retval != 0:
            log('synoindex FAILED for ' + path + ': ' +  ' '.join(p.stderr.split('\n')))
        # Reindex the whole thing, if we have a lull in new files
        if self.reindex_timer:
            self.reindex_timer.cancel()
        self.reindex_timer = LoggingTimer(30, self.reindex)
        self.reindex_timer.start()

    def is_relevant_file(self, path):
        (root, ext) = os.path.splitext(path)
        if ext.lower() in ['.jpg', '.jpeg', '.mpg', '.mp4']:
            return True
        return False

    def process_IN_CREATE(self, event):
        if self.is_relevant_file(event.pathname):
            log("Notified of new file: %s" % event.pathname)
            self.active[event.pathname] = LoggingTimer(3, self.process_file, (event.pathname,))
            self.active[event.pathname].start()
        
    def process_IN_CLOSE_WRITE(self, event):
        if self.is_relevant_file(event.pathname):
            log("Notified of file write: %s" % event.pathname)
            if event.pathname in self.active:
                self.active[event.pathname].cancel()
                self.active[event.pathname] = LoggingTimer(3, self.process_file, (event.pathname,))
                self.active[event.pathname].start()

    def process_IN_MOVED_TO(self, event):
        if self.is_relevant_file(event.pathname):
            log("Notified of file moved in: %s" % event.pathname)
            LoggingTimer(3, self.process_file, (event.pathname,)).start()
        
        
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


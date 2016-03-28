#
# Medio: Automatic media organizer for Synology Photo Station
# Copyright(c) 2016 Jonathan Poland
#

import re, os, time, sys, traceback, subprocess
import pyinotify
import ConfigParser
import Queue
from threading import Thread, _Timer

PKGDIR="/usr/syno/synoman/webman/3rdparty/Medio"
PHOTO_DIR = '/var/services/photo/'
LOG=os.path.join(PKGDIR, 'medio.log')

def log(msg):
    l = open(LOG, "a")
    l.write('[%s] %s\n' % (time.ctime(), str(msg)))

class Config(object):
    """A simple container to parse and feed back out INI-style config.  The config
       file is written via shell code, this is readonly."""
    def __init__(self):
        self.cfg = ConfigParser.SafeConfigParser()
        self.cfg.read(os.path.join(PKGDIR, 'cfg.ini'))
    
    @property
    def UI_SRCDIR(self):
        return self.cfg.get('UI', 'UI_SRCDIR')

    @property
    def UI_DSTDIR(self):
        return self.cfg.get('UI', 'UI_DSTDIR')

class Spawn(object):
    """A wrapper around subprocess just to save boilerplate"""
    def __init__(self, args, shell=False, env=None):
        handle = subprocess.Popen(args, stdin=open(os.devnull, 'r'), stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, close_fds=True, shell=shell, env=env)
        self.stdout, self.stderr = handle.communicate()
        self.retval = handle.wait()

class LoggingTimer(_Timer):
    """A threading.Timer that will catch exceptions in run() and log them to our
       global log file.  Without this, threads would throw and exit, but leave
       no trace."""
    def run(self):
        try:
            _Timer.run(self)
        except:
            err = traceback.format_exc(2)
            log(err)

class Worker(Thread):
    """A single thread to do most of the work.  Waits on a Queue for new work"""
    rename_re = re.compile(r"'(\S+)'\s+-->\s+'(\S+)'")
    reindex_timer = None
    cfg = None
    workq = None

    def __init__(self, cfg, workq):
        Thread.__init__(self)
        self.cfg = cfg
        self.workq = workq
        self.start()

    def reindex(self):
        """synoindex -n doesn't seem to be a reliable way to make sure things get
           indexed correctly.  So, call this to do a full reindex on our watched directory
           after a file (or set of files) have been processed"""
        cmd = ['/usr/syno/bin/synoindex', '-R', os.path.join(PHOTO_DIR, self.cfg.UI_SRCDIR)]
        p = Spawn(cmd)
        if p.retval != 0:
            log('synoindex reindex FAILED: ' +  ' '.join(p.stderr.split('\n')))
        log('Reindexing %s...' % os.path.join(PHOTO_DIR, self.cfg.UI_SRCDIR))
        self.reindex_timer = None

    def process_file(self, path):
        """This does the bulk of the work.  Calls exiftool to do the rename and synoindex 
           to tell DSM about it."""
        # Use exiftool to do the rename
        srcfile = os.path.join(PHOTO_DIR, self.cfg.UI_SRCDIR, path)
        dstfmt = os.path.join(PHOTO_DIR, self.cfg.UI_DSTDIR, r'%Y/%m_%b/%Y%m%d_%H%M%S%%c.%%e')
        dstfile = None
        cmd = [os.path.join(PKGDIR, 'exiftool'), '-v', '-r', '-d', dstfmt, 
                "-filename<filemodifydate", "-filename<createdate", 
                "-filename<datetimeoriginal", srcfile]
        p = Spawn(cmd)
        if p.retval != 0:
            log('exiftool FAILED for ' + path + ': ' +  ' '.join(p.stderr.split('\n')))
            return
        for line in p.stdout.split('\n'):
            m = self.rename_re.match(line)
            if m and m.group(1) == srcfile:
                dstfile = m.group(2)
                common = os.path.commonprefix([srcfile, dstfile])
                log('Moved %s to %s' % (os.path.relpath(srcfile, common), 
                                        os.path.relpath(dstfile, common)))
        if dstfile is None:
            log('exiftool succeeded, but no file rename information found')
            return
        # Tell synology it moved (synoindex)
        cmd = ['/usr/syno/bin/synoindex', '-n', dstfile, srcfile]
        p = Spawn(cmd)
        if p.retval != 0:
            log('synoindex FAILED for ' + os.path.dirname(srcfile) + ': ' +  ' '.join(p.stderr.split('\n')))
	# Also index directory it moved to
        cmd = ['/usr/syno/bin/synoindex', '-R', os.path.dirname(dstfile)]
        p = Spawn(cmd)
        if p.retval != 0:
            log('synoindex FAILED for ' + os.path.dirname(dstfile) + ': ' +  ' '.join(p.stderr.split('\n')))
        # Queue a reindex on everything, cancel any such existing timer
        if self.reindex_timer:
            self.reindex_timer.cancel()
        self.reindex_timer = LoggingTimer(30, self.reindex)
        self.reindex_timer.start()

    def run(self):
        errorCount = 0
        while errorCount < 5:
            try:
                path = self.workq.get()
                self.process_file(path)
                self.workq.task_done()
            except:
                errorCount += 1
                err = traceback.format_exc(2)
                log(err)
        log('Too many errors, Worker thread exiting')

class Watcher(Thread):
    """A thread to watch files that are in transit"""
    cfg = None
    workq = None
    watchq = None
    timer = None
    active = {}

    def __init__(self, cfg, workq, watchq):
        Thread.__init__(self)
        self.cfg = cfg
        self.workq = workq
        self.watchq = watchq
        self.start()

    def check_actives(self):
        # Check all actives
        now = time.time()
        for filepath, tstamp in self.active.items():
            if now - tstamp > 30:
                self.workq.put(filepath)
                del self.active[filepath]
        # Check again soon if there's more
        if len(self.active) > 0:
            if self.timer:
                self.timer.cancel()
            self.timer = LoggingTimer(5, self.check_actives)
            self.timer.start()

    def process_file(self, path):
        filesize = os.path.exists(path) and os.stat(path).st_size or 0
        if filesize > 0:
            self.active[path] = time.time()
            self.check_actives()

    def run(self):
        errorCount = 0
        while errorCount < 5:
            try:
                path = self.watchq.get()
                self.process_file(path)
                self.watchq.task_done()
            except:
                errorCount += 1
                err = traceback.format_exc(2)
                log(err)
        log('Too many errors, Watcher thread exiting')

class EventHandler(pyinotify.ProcessEvent):
    """This class handles our file change events queueing events to our work and watch queues"""
    cfg = None
    workq = None
    watchq = None

    def __init__(self, cfg, workq, watchq):
        self.cfg = cfg
        self.workq = workq
        self.watchq = watchq
        # Check for files we may have missed and queue them
        for entry in os.listdir(os.path.join(PHOTO_DIR, self.cfg.UI_SRCDIR)):
            if self.is_relevant_file(entry):
                self.watchq.put(os.path.join(PHOTO_DIR, self.cfg.UI_SRCDIR, entry))

    def is_relevant_file(self, path):
        """Return whether or not we care about this file type"""
        (root, ext) = os.path.splitext(path)
        if ext.lower() in ['.jpg', '.jpeg', '.mpg', '.mp4', '.png', '.mov']:
            return True
        return False

    def process_IN_CREATE(self, event):
        """We see this when we upload via the network (NFS, AFS, SMB)"""
        if self.is_relevant_file(event.pathname):
            self.watchq.put(event.pathname)
        
    def process_IN_CLOSE_WRITE(self, event):
        """We see lots of these per file when uploading via the network"""
        if self.is_relevant_file(event.pathname):
            self.watchq.put(event.pathname)

    def process_IN_MOVED_TO(self, event):
        """We see this when the DS photo app uploads stuff or we use file manager to move
           files in from somewhere else"""
        if self.is_relevant_file(event.pathname):
            self.workq.put(event.pathname)
        
if __name__ == '__main__':
    try:
        cfg = Config()
        workq = Queue.Queue()
        watchq = Queue.Queue()
        worker = Worker(cfg, workq)
        watcher = Watcher(cfg, workq, watchq)
        wm = pyinotify.WatchManager()
        notifier = pyinotify.Notifier(wm, EventHandler(cfg, workq, watchq))
        mask = pyinotify.IN_CREATE | pyinotify.IN_MOVED_TO | pyinotify.IN_CLOSE_WRITE
        wdd = wm.add_watch(os.path.join(PHOTO_DIR, cfg.UI_SRCDIR), mask)
        log('Source directory: %s' % os.path.join(PHOTO_DIR, cfg.UI_SRCDIR))
        log('Destination directory: %s' % os.path.join(PHOTO_DIR, cfg.UI_DSTDIR))
        log('Watching for changes...')
        notifier.loop()
    except:
        err = traceback.format_exc(2)
        log(err)


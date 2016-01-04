#
# exiftool -r -d DSTDIR/%Y/%m_%b/%Y%m%d_%H%M%S%%c.%%e "-filename<CreateDate" SRCDIR
#
import pyinotify
from threading import Timer

wm = pyinotify.WatchManager()

mask = pyinotify.IN_CREATE | pyinotify.IN_MOVED_TO 

def process_file(path):
    print "Process:", path

class EventHandler(pyinotify.ProcessEvent):
    def process_IN_CREATE(self, event):
        print "Creating:", event.pathname
        Timer(5, process_file, (event.pathname,)).start()
        
    def process_IN_MOVED_TO(self, event):
        print "Moved in:", event.pathname
        
    def process_IN_CLOSE_WRITE(self, event):
        print "Wrote:", event.pathname
        
if __name__ == '__main__':
    notifier = pyinotify.Notifier(wm, EventHandler())
    wdd = wm.add_watch('/volume1/photo/Jon phone/', mask)
    notifier.loop()


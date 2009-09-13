from collections import deque, defaultdict
from time import time
import sys
import threading

class Profiler:
    def __init__(self):
        self.callStack = defaultdict(deque)
        self.funcStats = defaultdict(lambda: [0, 0])
        self.active = False
        self.lock = threading.Lock()
        
        
    def start(self):
        sys.setprofile(self.event)
        threading.setprofile(self.event)
        self.active = True
        
        
    def stop(self):
        threading.setprofile(None)
        sys.setprofile(None)
        self.active = False
    
    
    def event(self, frame, event, arg):
        currentTime = time()
        code = frame.f_code
        if (not code.co_filename.endswith('threading.py')) or code.co_name == 'acquire' or code.co_name == 'release':
            func = (code.co_filename, code.co_firstlineno, code.co_name)
            thread = threading.currentThread().getName()
            if not self.active:
                #no longer active, lets try to teach that to the thread ;)
                sys.setprofile(None)
            else:
                #still active
                if thread not in self.callStack:
                    sys.setprofile(self.event)
                
                if event == 'call':
                    #entered func
                    self.callStack[thread].append((time(), func))
                    
                elif event == 'return':
                    #returned from func
                    if len(self.callStack[thread]) > 0:
                        startTime, oldFunc = self.callStack[thread].pop()
                        assert oldFunc == func
                        self.funcStats[func][0] += currentTime - startTime
                        self.funcStats[func][1] += 1
        
    
    def printStats(self):
        stats = [(value[0], value[1], func) for func, value in self.funcStats.iteritems()]
        stats.sort()
        stats.reverse()
        print 'CumTime         NumCalls    Other'
        for cumTime, numCalls, func in stats:
            print '%14f  %10i  File "%s", line %i, in %s' % (cumTime, numCalls, func[0], func[1], func[2])
    
    
if __name__ == '__main__':
    test = Profiler()
    test.start()
    #d = threading.Lock()
    #d.acquire()
    #d.release()
    d = threading.RLock()
    d.acquire()
    d.release()
    test.stop()
    test.printStats()
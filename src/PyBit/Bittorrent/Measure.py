"""
Copyright 2009  Blub

Measure, a class for measuring the bandwidth rate.
This file is part of PyBit.

PyBit is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published
by the Free Software Foundation, version 2 of the License.

PyBit is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with PyBit.  If not, see <http://www.gnu.org/licenses/>.
"""

import threading
from collections import deque
from time import time

class Measure:
    def __init__(self, scheduler, interval, parents=[]):
        self.sched = scheduler
        self.interval = interval
        
        self.createTime = time()
        
        self.transferedBytes = 0
        self.totalTransferedBytes = 0
        self.totalTransferedPayloadBytes = 0
        self.transferTimes = deque()
        self.transferAmounts = deque()
        self.parents = parents
        
        self.eventId = None
        
        self.lock = threading.RLock()
        self._start()
        
        
    ##internal
    
    def _start(self):
        if self.eventId is None:
            self.eventId = self.sched.scheduleEvent(self.cleanOldTransfers, timedelta=1, repeatdelta=1)
        

    def _stop(self):
        self.sched.removeEvent(self.eventId)
        self.eventId = None
        
        while len(self.transferTimes)>0:
            self.transferedBytes -= self.transferAmounts[0]
            del self.transferTimes[0]
            del self.transferAmounts[0]
    
    
    ##external

    def addParent(self, parent):
        self.lock.acquire()
        if not parent in self.parents:
            self.parents.append(parent)
        self.lock.release()
            

    def delParent(self, parent):
        self.lock.acquire()
        if parent in self.parents:
            del self.parents[self.parent.index(parent)]
        self.lock.release()
            

    def hasParent(self, parent):
        self.lock.acquire()
        value = parent in self.parents
        self.lock.release()
        return value
    

    def updateRate(self, amount):
        self.lock.acquire()
        #parents
        for parent in self.parents:
            parent.updateRate(amount)
        #local
        self.transferTimes.append(time())
        self.transferAmounts.append(amount)
        self.transferedBytes += amount
        self.totalTransferedBytes += amount
        
        self.lock.release()


    def updatePayloadCounter(self, amount):
        self.lock.acquire()
        for parent in self.parents:
            parent.updatePayloadCounter(amount)
        self.totalTransferedPayloadBytes += amount
        self.lock.release()


    def getCurrentRate(self):
        self.lock.acquire()
        value = self.transferedBytes/(self.interval*1.0)
        self.lock.release()
        return value


    def getTotalTransferedBytes(self):
        self.lock.acquire()
        value = self.totalTransferedBytes
        self.lock.release()
        return value
    

    def getTotalTransferedPayloadBytes(self):
        self.lock.acquire()
        value = self.totalTransferedPayloadBytes
        self.lock.release()
        return value
    
    
    def getAverageRate(self):
        self.lock.acquire()
        value = self.totalTransferedBytes / max(1.0, (time() - self.createTime*1.0))
        if value > 0:
            value /= 1024.0
        self.lock.release()
        return value
    
    
    def getAveragePayloadRate(self):
        self.lock.acquire()
        value = self.totalTransferedPayloadBytes / max(1.0, (time() - self.createTime*1.0))
        if value > 0:
            value /= 1024.0
        self.lock.release()
        return value
    

    def cleanOldTransfers(self):
        self.lock.acquire()
        currentTime = time()
        if len(self.transferTimes)>0:
            while currentTime - self.transferTimes[0] > self.interval:
                del self.transferTimes[0]
                self.transferedBytes -= self.transferAmounts.popleft()
                if len(self.transferTimes)==0:
                    break
        self.lock.release()
        
    def start(self):
        self.lock.acquire()
        self._start()
        self.lock.release()
        

    def stop(self):
        self.lock.acquire()
        self._stop()
        self.lock.release()


"""
Copyright 2009  Blub

EventScheduler, a general class for scheduling and later executing events.
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

from copy import copy
from heapq import heappush, heappop
from time import sleep, time
import heapq
import logging
import threading

from Utilities import logTraceback




class EventSchedulerException(Exception):
    pass




class EventScheduler:
    def __init__(self):
        self.eventQueue = []
        self.eventDict = {}
        self.eventId = 0
        self.eventNum = 0
        
        self.log = logging.getLogger('EventScheduler')
        
        self.editLock = threading.RLock()
        self.queueChangeEvent = threading.Event()        
        self.runLock = threading.RLock()    
        
        self.shouldStop = False        
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        
        
    ##internal event functions
    
    def _addEvent(self, event):
        self.editLock.acquire()
        
        #add event num to event
        event['num'] = self.eventNum
        
        #add event to dict
        eventId = self.eventId
        self.eventId += 1
        self.eventDict[eventId] = event
        
        #add event to queue
        heappush(self.eventQueue, (event['time'], self.eventNum, eventId))
        self.eventNum += 1
        
        if self.eventQueue[0][2] == eventId:
            #soonest event changed, notify thread
            self.queueChangeEvent.set()
        
        self.editLock.release()
        return eventId
    
    
    def _getEvent(self): 
        self.editLock.acquire()
        event = None
        shouldExec = False
        
        #get soonest valid event, if any
        while event is None and len(self.eventQueue) > 0:
            targetTime, eventNum, eventId = self.eventQueue[0] #take soonest event
            
            if not eventId in self.eventDict:
                #inactive event, remove
                heappop(self.eventQueue)
                event = None
                
            else:
                #event is known
                event = self.eventDict[eventId]
                
                if eventNum != event['num']:
                    #event was rescheduled to an earlier time
                    heappop(self.eventQueue)
                    event = None
                    
                elif targetTime != event['time']:
                    #event was rescheduled to a later time
                    heappop(self.eventQueue)
                    heappush(self.eventQueue, (event['time'], eventNum, eventId))
                    event = None
              
        if event is not None:
            if event['time'] <= time():
                #should be executed
                heappop(self.eventQueue)
                shouldExec = True
                
                if not event['repeat']:
                    #remove for good
                    del self.eventDict[eventId]
                    
                else:
                    #reschedule
                    newEvent = copy(event)
                    if newEvent['catchUpRepeats']:
                        newEvent['time'] += newEvent['repeatdelta']
                    else:
                        newEvent['time'] = time() + newEvent['repeatdelta']
                    newEvent['num'] = self.eventNum
                    self.eventDict[eventId] = newEvent
                    heappush(self.eventQueue, (newEvent['time'], self.eventNum, eventId))
                    self.eventNum += 1
        
        self.queueChangeEvent.clear() #clear queue change event
        self.editLock.release()
        return event, shouldExec
    
    
    def _rescheduleEvent(self, eventId, relativeTimedelta=None, timedelta=None, timestamp=None):
        self.editLock.acquire()
        
        if eventId in self.eventDict:
            #event exists
            event = self.eventDict[eventId]
            oldTime = event['time']
            
            #apply change
            if timestamp is not None:
                #absolute target
                newTime = timestamp
                
            elif timedelta is not None:
                #absolute target - relative to the current time
                newTime = time() + timedelta
                
            else:
                #relative change, get current event time
                newTime = oldTime + relativeTimedelta
                
            if oldTime <= newTime:
                #rescheduled to a later time, the scheduler will do the work once necessary
                event['time'] = newTime
                
            else:
                #rescheduled to an earlier time, need to immediately adapt the queue
                event = copy(event)
                event['time'] = newTime
                event['num'] = self.eventNum
                self.eventDict[eventId] = event
                heappush(self.eventQueue, (newTime, self.eventNum, eventId))
                self.eventNum += 1
            
        self.editLock.release()
        
        
    def _changeEvent(self, eventId, repeatdelta, catchUpLateRepeats):
        self.editLock.acquire()
        if eventId in self.eventDict:
            event = self.eventDict[eventId]
            if catchUpLateRepeats is not None:
                event['catchUpRepeats'] = catchUpLateRepeats
            if repeatdelta is not None:
                if repeatdelta >= 0:
                    event['repeat'] = True
                    event['repeatdelta'] = repeatdelta 
                    event['catchUpRepeats'] = event.get('catchUpRepeats', False)
                else:
                    event['repeat'] = False
                    event.pop('repeatdelta', None)
                    event.pop('catchUpRepeats', None)
        self.editLock.release()
        
        
    def _removeEvent(self, eventId):
        self.editLock.acquire()
        if eventId in self.eventDict:
            del self.eventDict[eventId]
        self.editLock.release()
        
        
    def _removeAllEvents(self):
        self.editLock.acquire()
        self.eventQueue = []
        self.eventDict = {}
        self.editLock.release()
        
    ##internal thread functions
        
    def _wait(self, waittime=None):        
        self.runLock.release()
        #self.log.debug('waiting for %s seconds', str(waittime))
        #start = time()
        if waittime is None:
            #wait until queue got a new item
            self.queueChangeEvent.wait()
        else:
            #only wait until the queue was changed or the waittime passed, whatever happens first
            self.queueChangeEvent.wait(waittime)
        #self.log.debug('waited for %f seconds', time()-start)
        self.runLock.acquire()
        
        
    ##thread loop
        
    def run(self):
        try:
            self.runLock.acquire()
            while not self.shouldStop:
                event, shouldExec = self._getEvent()
                if event is None:
                    #nothing in the queue
                    self._wait()
                else:
                    if shouldExec:
                        #execute
                        try:
                            #self.log.debug("Executing event:\nfunc: %s\nargs: %s\nkws: %s", str(event['task']), str(event['args']), str(event['kw']))
                            apply(event['task'], event['args'], event['kw'])
                        except:
                            self.log.error('Execution of event failed:\n%s', logTraceback())
                    else:
                        #wait
                        self._wait(event['time'] - time())
            
            self.log.debug('Stopping')
            self.thread = None
            self.runLock.release()
        except:
            self.log.error('Error in main loop:\n%s', logTraceback())
        
        
    ##external functions
            
    def scheduleEvent(self, task, timestamp=None, timedelta=None, funcArgs=[], funcKw={}, repeatdelta=None, catchUpLateRepeats=False):
        if (timestamp is not None) and (timedelta is not None):
            raise EventSchedulerException('Only either a timestamp or a timedelta may be given')
        
        elif (timestamp is None) and (timedelta is not None):
            eventTime = time() + timedelta
            
        elif (timestamp is not None) and (timedelta is None):
            eventTime = timestamp
            
        else:
            eventTime = time()
            
        event = {'task':task,\
                 'time':eventTime,\
                 'args':funcArgs,\
                 'kw':funcKw}
                
        if repeatdelta is None:
            event['repeat'] = False
        else:
            event['repeat'] = True
            event['repeatdelta'] = repeatdelta 
            event['catchUpRepeats']= catchUpLateRepeats
            
        return self._addEvent(event)
    
    
    def rescheduleEvent(self, eventId, timestamp=None, timedelta=None, relativeTimedelta=None):
        if (timestamp is not None) + (timedelta is not None) + (relativeTimedelta is not None) > 1:
            raise EventSchedulerException('Only one of "timestamp", "timedelta" and "relativeTimedelta" may be given at once')
        
        elif (timestamp is None) and (timedelta is None) and (relativeTimedelta is None):
            timestamp = time()
            
        self._rescheduleEvent(eventId, timestamp=timestamp, timedelta=timedelta, relativeTimedelta=relativeTimedelta)
        
        
    def changeEvent(self, eventId, repeatdelta=None, catchUpLateRepeats=None):
        self._changeEvent(eventId, repeatdelta, catchUpLateRepeats)
        
        
    def removeEvent(self, eventId, sync=False):
        self._removeEvent(eventId)
        if sync:
            self.runLock.acquire()
            self.runLock.release()
        
        
    def removeAllEvents(self):
        self._removeAllEvents()
        
        
    def pause(self):
        """
        pauses all thread related work and guarantees that thread is
        inside the _wait function after returning. Any function which
        interacts with the thread will block until resume was called,
        even stop!
        """
        self.runLock.acquire()
        

    def resume(self):
        self.runLock.release()
        
        
    def stop(self, deleteEvents=True):
        self.runLock.acquire()
        self.shouldStop = True #set flag
        if deleteEvents:
            self._removeAllEvents() #empty eventlist
        self.queueChangeEvent.set() #set event in case thread is sleeping
        thread = self.thread
        self.runLock.release()
        thread.join() #wait for thread to terminate
        
        
    def start(self):
        self.runLock.acquire()
        shouldStop = False
        if self.thread is None:
            self.thread = threading.Thread(target=self.run)
            self.thread.start()
        self.runLock.release()


if __name__=='__main__':
    def testEvent(*args, **kw):
        print 'TIME:',time()
        print 'ARGS', args
        print 'KW',kw
        
    sched = EventScheduler()
    print 'Pausing Scheduler'
    sched.pause()    
    print 'Done'
    
    from random import shuffle
    timedels = range(1, 65536)
    shuffle(timedels)
    start = time()
    print 'Current time:', start
    print 'Scheduling events in 1,2,3,4, ... 65536 seconds ...'
    for i in timedels:
        sched.scheduleEvent(testEvent, timestamp=start+i, funcArgs=['arg1','arg2'], funcKw={'Key':'Value','TimeDelta':i, 'TargetTime':start+i})
    print 'Done after',time() - start, 'seconds'
    
    print 'Activating Scheduler ...',
    sched.resume()
    print 'Done, sleeping 10 seconds...'
    sleep(10)
    print 'Done, removing all Events, pausing scheduler ...'
    sched.removeAllEvents()
    sched.pause()
    print 'Done, scheduling repeated task ...'
    eventId = sched.scheduleEvent(testEvent, timedelta=2, funcArgs=['arg1','arg2'], funcKw={'Key':'Value','TimeDelta':2}, repeatdelta=2)
    sched.rescheduleEvent(eventId, timedelta=8)
    print 'Done, activating scheduler ...'
    sched.resume()
    print 'Done, sleeping 20 seconds...'
    sleep(20)
    print 'Done, removing all Events, pausing scheduler ...'
    sched.removeAllEvents()
    sched.pause()
    print 'Done, scheduling task in 15 seconds'
    eventId = sched.scheduleEvent(testEvent, timedelta=15, funcArgs=['arg1','arg2'], funcKw={'Key':'Value','TimeDelta':15, 'TargetTime':time()+15})
    print 'Done, activating scheduler ...'
    sched.resume()
    print 'Done, rescheduling task to run 10 seconds earlier'
    sched.rescheduleEvent(eventId, relativeTimedelta=-10)
    print 'Done, waiting 20 seconds'
    sleep(20)
    print 'Done, terminating ...'
    sched.stop()
    print 'Done'
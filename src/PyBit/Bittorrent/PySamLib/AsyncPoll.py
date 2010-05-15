"""
Copyright 2010  Blub

AsnycPoll, a simple class emulating the poll()-interface using AsyncSocketManager.
This file is part of PySamLib.

PySamLib is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published
by the Free Software Foundation, version 2.1 of the License.

PySamLib is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with PySamLib.  If not, see <http://www.gnu.org/licenses/>.
"""


import select


POLLIN = select.POLLIN
POLLPRI = select.POLLPRI
POLLOUT = select.POLLOUT
POLLERR = select.POLLERR
POLLHUP = select.POLLHUP
POLLNVAL = select.POLLNVAL

POLLRECV = POLLIN | POLLPRI
POLLSEND = POLLOUT
POLLERROR = POLLERR | POLLHUP | POLLNVAL


class SelectingAsyncPoll:
    def __init__(self, sockManager):
        self.sockManager = sockManager
        self.recvInterest = set()
        self.sendInterest = set()
        self.errorInterest = set()
        
    def register(self, sock, eventmask):
        if not isinstance(sock, (int, long)):
            sock = sock.fileno()
            
        #remove
        self.recvInterest.discard(sock)
        self.sendInterest.discard(sock)
        self.errorInterest.discard(sock)
        
        #add again            
        if eventmask & POLLRECV != 0:
            self.recvInterest.add(sock)
            
        if eventmask & POLLSEND != 0:
            self.sendInterest.add(sock)
            
        if eventmask & POLLERROR != 0:
            self.errorInterest.add(sock)
            
        
    def unregister(self, sock):
        if not (type(sock) == int or type(sock)==long):
            sock = sock.fileno()
            
        #remove
        self.recvInterest.discard(sock)
        self.sendInterest.discard(sock)
        self.errorInterest.discard(sock)
        
        
    def poll(self, timeout=None):
        if timeout is not None:
            timeout = timeout/1000.0
        readList, writeList, errorList = self.sockManager.select(self.recvInterest, self.sendInterest, self.errorInterest, timeout)
        
        connEvents = {}
        
        for conn in readList:
            connEvents[conn] = POLLIN
            
        for conn in writeList:
            connEvents[conn] = (connEvents.get(conn,0) | POLLOUT)
                
        for conn in errorList:
            connEvents[conn] = (connEvents.get(conn,0) | POLLERROR)
            
        events = [(conn, event) for conn, event in connEvents.iteritems()]
        return events




class NativeAsyncPoll:
    def __init__(self, sockManager):
        self.sockManager = sockManager
        self.pollObj = select.poll()
        self.errorInterestSet = set()
        
    
    def register(self, sock, eventmask):
        if not isinstance(sock, (int, long)):
            sock = sock.fileno()
        
        #check for POLLERROR
        if eventmask & POLLERROR != 0:
            self.errorInterestSet.add(sock)
        else:
            self.errorInterestSet.discard(sock)
            
        #register id
        self.pollObj.register(sock, eventmask)
        
        
    def unregister(self, sock):
        if not (type(sock) == int or type(sock)==long):
            sock = sock.fileno()
        
        self.errorInterestSet.discard(sock)
        self.pollObj.unregister(sock)
        
        
    def poll(self, timeout=None):
        events = self.pollObj.poll(timeout)                                   #get the real socket events
        events, failedConns = self.sockManager.checkPollEventResults(events)  #let the sockManager check for failed/invalid conns
        events.extend([(realSockNum, POLLNVAL) for realSockNum, eventmask in failedConns if realSockNum in self.errorInterestSet]) #add all unknown ids
        return events
    
    
    

try:
    testObj = select.poll()
    del testObj
    AsyncPoll = NativeAsyncPoll
except:
    AsyncPoll = SelectingAsyncPoll

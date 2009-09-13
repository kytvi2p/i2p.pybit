"""
Copyright 2008  Blub

SamSocket, a collection of classes that emulate normal socket interfaces.
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

from time import sleep

POLLIN = 1
POLLPRI = 2
POLLOUT = 4
POLLERR = 8
POLLHUP = 16
POLLNVAL = 32

POLLREAD = POLLIN | POLLPRI
POLLWRITE = POLLOUT
POLLERROR = POLLERR | POLLHUP | POLLNVAL

class SamPoll:
    def __init__(self, sam):
        self.sam = sam
        self.recvInterest = set()
        self.sendInterest = set()
        self.errorInterest = set()
        
    def register(self, sock, eventmask):
        if not type(sock)==int:
            sock = sock.fileno()
            
        #remove
        self.recvInterest.discard(sock)
        self.sendInterest.discard(sock)
        self.errorInterest.discard(sock)
        
        #add again            
        if eventmask & (POLLIN | POLLPRI) != 0:
            self.recvInterest.add(sock)
            
        if eventmask & POLLOUT != 0:
            self.sendInterest.add(sock)
            
        if eventmask & (POLLERR | POLLHUP | POLLNVAL) != 0:
            self.errorInterest.add(sock)
        
    def unregister(self, sock):
        if not type(sock)==int:
            sock = sock.fileno()
            
        #remove
        self.recvInterest.discard(sock)
        self.sendInterest.discard(sock)
        self.errorInterest.discard(sock)
        
    def poll(self, timeout=None):
        if timeout is not None:
            timeout = timeout/1000.0
        readList, writeList, errorList = self.sam.select(self.recvInterest, self.sendInterest, self.errorInterest, timeout)
        
        connEvents = {}
        
        for conn in readList:
            connEvents[conn] = POLLREAD
            
        for conn in writeList:
            if conn in connEvents:
                connEvents[conn] |= POLLWRITE
            else:
                connEvents[conn] = POLLWRITE
                
        for conn in errorList:
            if conn in connEvents:
                connEvents[conn] |= POLLERROR
            else:
                connEvents[conn] = POLLERROR
                
        events = []
        for conn, event in connEvents.iteritems():
            events.append((conn, event))
        return events
    
    
class SamSocketError(Exception):
    pass

class SamInvalidArgument(Exception):
    pass
            
            
class SamSocket:
    def __init__(self, sam, destNum, sockNum=None, remoteDest='', type=''):
        self.sam = sam
        self.destNum = destNum
        self.sockNum = sockNum
        self.timeout = None
        self.ownDest = None
        self.remoteDest = remoteDest
        self.type = type
        
        if self.sockNum is not None:
            if self.type=='':
                self.type = self.sam.getSamSocketType(self.sockNum)[:3]
            if self.remoteDest=='' and self.type=='tcp':
                self.remoteDest = self.sam.getSamSocketRemoteDestination(self.sockNum)           
    
    
    ##helpers##
    
    def fileno(self):
        return self.sockNum
    
    def getpeername(self):
        if not self.type=='tcp':
            raise SamInvalidArgument("getpeername() may only be called on tcp sockets")
        return self.remoteDest
    
    def getsockname(self):
        if self.ownDest is None:
            self.ownDest = self.sam.getOwnDestination(destNum=self.destNum)
        return self.ownDest
    
    def setblocking(self, block):
        if block==0:
            self.timeout = -1
        else:
            self.timeout = None
            
    def settimeout(self, timeout):
        if timeout==0:
            self.timeout = -1
        else:
            self.timeout = timeout
            
    def gettimeout(self):
        return self.timeout
    
    def getUsedInBufferSpace(self):
        if self.sockNum is None:
            raise SamSocketError("Not connected")
        
        if not self.type=='tcp':
            raise SamInvalidArgument("getUsedInBufferSpace() may only be called on tcp sockets")
        
        return self.sam.getSamSocketUsedInBufferSpace(self.sockNum)
    
    def getFreeOutBufferSpace(self):
        if self.sockNum is None:
            raise SamSocketError("Not connected")
        
        if not self.type=='tcp':
            raise SamInvalidArgument("getFreeOutBufferSpace() may only be called on tcp sockets")
        
        return self.sam.getSamSocketFreeOutBufferSpace(self.sockNum)        
    
    
    ##data transfer, accepting conns, ...##
        
    def connect(self, targetDest, inMaxQueueSize=32768, outMaxQueueSize=32768, inRecvLimitThreshold=None):
        if self.sockNum is not None:
            raise SamSocketError("Already either listening or connected")
        
        self.sockNum = self.sam.connect(self.destNum, targetDest, inMaxQueueSize, outMaxQueueSize, inRecvLimitThreshold)
        self.remoteDest = targetDest
        self.type = 'tcp'
        if not self.timeout==-1:
            #blocking call
            readList, writeList, errorList = self.sam.select(set(), set((self.sockNum,)), set((self.sockNum,)), timeout=self.timeout)
            
            if self.sockNum in errorList:
                raise SamSocketError("Connect failed")
            
    def bind(self, destNum):
        self.destNum = destNum
        
    def listen(self, addOld=False):
        if self.sockNum is not None:
            raise SamSocketError("Already either listening or connected")
        
        self.sockNum = self.sam.listen(self.destNum, addOld)
    
    def accept(self, max=None):
        if self.sockNum is None:
            #not listening
            raise SamSocketError("Not a listening socket")
        
        if not self.timeout==-1:
            #blocking call
            readList, writeList, errorList = self.sam.select(set((self.sockNum,)), set(), set((self.sockNum,)), timeout=self.timeout)
            
            if self.sockNum in errorList:
                raise SamSocketError("Listening socket lost")
            
        if max is None:
            #compat mode
            newConn = self.sam.accept(self.sockNum, max=1)
            if len(newConn)>0:
                result = newConn[0]
            else:
                if self.timeout==-1:
                    raise SamSocketError("Would block")
                result = (None, None)
        else:
            #normal
            result = self.sam.accept(self.sockNum, max)

        return result
        
    def send(self, data):
        if self.sockNum is None:
            raise SamSocketError("Not connected")
        
        if self.type=='udp':
            raise SamInvalidArgument("send() may only be called on tcp or raw sockets")
        
        if not self.timeout==-1:
            #blocking call
            readList, writeList, errorList = self.sam.select(set(), set((self.sockNum,)), set((self.sockNum,)), timeout=self.timeout)
            
            if self.sockNum in errorList:
                raise SamSocketError("Connection failed")
            
        bytesSend = self.sam.send(self.sockNum, data)
        return bytesSend
    
    def sendto(self, data, target):
        if self.sockNum is None:
            raise SamSocketError("Not connected")
        
        if not self.type=='udp':
            raise SamInvalidArgument("sendto() may only be called on udp sockets")
        
        if not self.timeout==-1:
            #blocking call
            readList, writeList, errorList = self.sam.select(set(), set((self.sockNum,)), set((self.sockNum,)), timeout=self.timeout)
            
            if self.sockNum in errorList:
                raise SamSocketError("Connection failed")
            
        bytesSend = self.sam.send(self.sockNum, data, target=target)
        return bytesSend
    
    def sendall(self, data):
        bytesSend = self.send(data)
        while not bytesSend==len(data):
            sleep(0.5)
            bytesSend += self.send(data[bytesSend:])
        return bytesSend
    
    def recv(self, max=-1, peekOnly=False):
        if self.sockNum is None:
            raise SamSocketError("Not connected")
        
        if self.type=='udp':
            raise SamInvalidArgument("recv() may only be called on tcp or raw sockets")
        
        if not self.timeout==-1:
            #blocking call
            readList, writeList, errorList = self.sam.select(set((self.sockNum,)), set(), set((self.sockNum,)), timeout=self.timeout)
            
            if self.sockNum in errorList:
                raise SamSocketError("Connection failed")
            
        data = self.sam.recv(self.sockNum, max, peekOnly)
        return data
    
    def recvfrom(self, max=None, peekOnly=False):
        if self.sockNum is None:
            raise SamSocketError("Not connected")
        
        if not self.type=='udp':
            raise SamInvalidArgument("recvfrom() may only be called on udp sockets")
        
        if not self.timeout==-1:
            #blocking call
            readList, writeList, errorList = self.sam.select(set((self.sockNum,)), set(), set((self.sockNum,)), timeout=self.timeout)
            
            if self.sockNum in errorList:
                raise SamSocketError("Connection failed")
            
        if max is None:
            #compat
            data = self.sam.recv(self.sockNum, 1, peekOnly)
            if len(data)==0:
                if self.timeout==-1:
                    raise SamSocketError("Would block")
                data = (None, None)
            else:
                data = data[0]
        else:
            #normal
            data = self.sam.recv(self.sockNum, max, peekOnly)
            
        return data
    
    def recvfrom_into(self, buffer, peekOnly=False):
        data, dest = self.recvfrom(peekOnly=peekOnly)
        buffer.write(data)
        return len(data), dest
    
    def recv_into(self, buffer, max, peekOnly=False):
        data = self.recv(max, peekOnly)
        buffer.write(data)
        return len(data)
    
    def close(self, forceClose=False):
        if self.sockNum is None:
            raise SamSocketError("Not connected")
        
        self.sam.close(self.sockNum, forceClose)
        
      

    


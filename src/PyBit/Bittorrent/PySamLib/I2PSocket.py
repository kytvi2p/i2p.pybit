"""
Copyright 2009  Blub

I2PSocket, a collection of classes which emulate normal socket interfaces.
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

class I2PPoll:
    def __init__(self, sockManager):
        self.sockManager = sockManager
        self.recvInterest = set()
        self.sendInterest = set()
        self.errorInterest = set()
        
    def register(self, sock, eventmask):
        if not (type(sock) == int or type(sock)==long):
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
    
    
class I2PSocketError(Exception):
    pass

class I2PInvalidArgument(Exception):
    pass
            
            
class I2PSocket:
    def __init__(self, sockManager, destId, sockId=None, remoteDest='', type=''):
        self.sockManager = sockManager
        self.destId = destId
        self.sockId = sockId
        self.timeout = None
        self.ownDest = None
        self.remoteDest = remoteDest
        self.type = type
        
        if self.sockId is not None:
            if self.type=='':
                self.type = self.sockManager.getI2PSocketType(self.sockId)[:3]
            if self.remoteDest=='' and self.type=='tcp':
                self.remoteDest = self.sockManager.getI2PSocketRemoteDestination(self.sockId)           
    
    
    ##helpers##
    
    def fileno(self):
        return self.sockId
    
    
    def getpeername(self):
        if not self.type=='tcp':
            raise I2PInvalidArgument("getpeername() may only be called on tcp sockets")
        return self.remoteDest
    
    
    def getsockname(self):
        if self.ownDest is None:
            self.ownDest = self.sockManager.getOwnDestination(destId=self.destId)
        return self.ownDest
    
    
    def setblocking(self, block):
        if block == 0:
            self.timeout = -1
        else:
            self.timeout = None
            
            
    def settimeout(self, timeout):
        if timeout == 0:
            self.timeout = -1
        else:
            self.timeout = timeout
            
            
    def gettimeout(self):
        return self.timeout
    
    
    def getUsedInBufferSpace(self):
        if self.sockId is None:
            raise I2PSocketError("Not connected")
        
        if not self.type=='tcp':
            raise I2PInvalidArgument("getUsedInBufferSpace() may only be called on tcp sockets")
        
        return self.sockManager.getI2PSocketUsedInBufferSpace(self.sockId)
    
    
    def getFreeOutBufferSpace(self):
        if self.sockId is None:
            raise I2PSocketError("Not connected")
        
        if not self.type=='tcp':
            raise I2PInvalidArgument("getFreeOutBufferSpace() may only be called on tcp sockets")
        
        return self.sockManager.getI2PSocketFreeOutBufferSpace(self.sockId)        
    
    
    ##data transfer, accepting conns, ...##
        
    def connect(self, remoteDest, inMaxQueueSize=None, outMaxQueueSize=None, inRecvLimitThreshold=None):
        if self.sockId is not None:
            raise I2PSocketError("Already either listening or connected")
        
        self.sockId = self.sockManager.connect(self.destId, remoteDest, inMaxQueueSize, outMaxQueueSize, inRecvLimitThreshold)
        self.remoteDest = remoteDest
        self.type = 'tcp'
        if not self.timeout==-1:
            #blocking call
            readList, writeList, errorList = self.sockManager.select(set(), set((self.sockId,)), set((self.sockId,)), timeout=self.timeout)
            
            if self.sockId in errorList:
                raise I2PSocketError("Connect failed")
            
            
    def bind(self, destId):
        self.destId = destId
        
        
    def listen(self, addOld=False):
        if self.sockId is not None:
            raise I2PSocketError("Already either listening or connected")
        
        self.sockId = self.sockManager.listen(self.destId, addOld)
        
    
    def accept(self, max=None):
        if self.sockId is None:
            #not listening
            raise I2PSocketError("Not a listening socket")
        
        if not self.timeout==-1:
            #blocking call
            readList, writeList, errorList = self.sockManager.select(set((self.sockId,)), set(), set((self.sockId,)), timeout=self.timeout)
            
            if self.sockId in errorList:
                raise I2PSocketError("Listening socket lost")
            
        if max is None:
            #compat mode
            newConn = self.sockManager.accept(self.sockId, max=1)
            if len(newConn) > 0:
                result = newConn[0]
            else:
                if self.timeout==-1:
                    raise I2PSocketError("Would block")
                result = (None, None)
        else:
            #normal
            result = self.sockManager.accept(self.sockId, max)

        return result
    
        
    def send(self, data):
        if self.sockId is None:
            raise I2PSocketError("Not connected")
        
        if self.type=='udp':
            raise I2PInvalidArgument("send() may only be called on tcp or raw sockets")
        
        if not self.timeout==-1:
            #blocking call
            readList, writeList, errorList = self.sockManager.select(set(), set((self.sockId,)), set((self.sockId,)), timeout=self.timeout)
            
            if self.sockId in errorList:
                raise I2PSocketError("Connection failed")
            
        bytesSend = self.sockManager.send(self.sockId, data)
        return bytesSend
    
    
    def sendto(self, data, target):
        if self.sockId is None:
            raise I2PSocketError("Not connected")
        
        if not self.type=='udp':
            raise I2PInvalidArgument("sendto() may only be called on udp sockets")
        
        if not self.timeout==-1:
            #blocking call
            readList, writeList, errorList = self.sockManager.select(set(), set((self.sockId,)), set((self.sockId,)), timeout=self.timeout)
            
            if self.sockId in errorList:
                raise I2PSocketError("Connection failed")
            
        bytesSend = self.sockManager.send(self.sockId, data, target=target)
        return bytesSend
    
    
    def sendall(self, data):
        bytesSend = self.send(data)
        while not bytesSend == len(data):
            sleep(0.5)
            bytesSend += self.send(data[bytesSend:])
        return bytesSend
    
    
    def recv(self, max=-1, peekOnly=False):
        if self.sockId is None:
            raise I2PSocketError("Not connected")
        
        if self.type=='udp':
            raise I2PInvalidArgument("recv() may only be called on tcp or raw sockets")
        
        if not self.timeout==-1:
            #blocking call
            readList, writeList, errorList = self.sockManager.select(set((self.sockId,)), set(), set((self.sockId,)), timeout=self.timeout)
            
            if self.sockId in errorList:
                raise I2PSocketError("Connection failed")
            
        data = self.sockManager.recv(self.sockId, max, peekOnly)
        return data
    
    
    def recvfrom(self, max=None, peekOnly=False):
        if self.sockId is None:
            raise SamSocketError("Not connected")
        
        if not self.type=='udp':
            raise I2PInvalidArgument("recvfrom() may only be called on udp sockets")
        
        if not self.timeout==-1:
            #blocking call
            readList, writeList, errorList = self.sockManager.select(set((self.sockId,)), set(), set((self.sockId,)), timeout=self.timeout)
            
            if self.sockId in errorList:
                raise I2PSocketError("Connection failed")
            
        if max is None:
            #compat
            data = self.sockManager.recv(self.sockId, 1, peekOnly)
            if len(data)==0:
                if self.timeout==-1:
                    raise I2PSocketError("Would block")
                data = (None, None)
            else:
                data = data[0]
        else:
            #normal
            data = self.sockManager.recv(self.sockId, max, peekOnly)
            
        return data
    
    def recvfrom_into(self, buffer, peekOnly=False):
        data, dest = self.recvfrom(peekOnly=peekOnly)
        buffer.write(data)
        return len(data), dest
    
    
    def recv_into(self, buffer, max, peekOnly=False):
        data = self.recv(max, peekOnly)
        buffer.write(data)
        return len(data)
    
    
    def close(self, force=False):
        if self.sockId is None:
            raise I2PSocketError("Not connected")
        
        self.sockManager.close(self.sockId, force)
        
      

    


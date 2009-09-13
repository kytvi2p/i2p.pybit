"""
Copyright 2009  Blub

I2PSocketStatus, a class which stores which i2pSocket may recv or send and which ones failed
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

class I2PSocketStatus:
    def __init__(self, event):
        self.event = event
        
        self.all = set()
        self.sendable = set()
        self.recvable = set()
        self.errored = set()
        
        self.uniqueOutId = 1
        self.uniqueInId = -1
        
        self.connIdToConnInfo = {}
        
        
    ##external functions - connections
        
    def addConn(self, destId, connType, direction):
        #get id
        if direction == 'out':
            connId = self.uniqueOutId
            self.uniqueOutId += 1
        else:
            connId = self.uniqueInId
            self.uniqueInId -= 1
            
        self.connIdToConnInfo[connId] = (destId, connType)
        
        self.all.add(connId)
        return connId
        
        
    def removeConn(self, connId):
        self.all.remove(connId)
        self.sendable.discard(connId)
        self.recvable.discard(connId)
        self.errored.discard(connId)
        
        del self.connIdToConnInfo[connId]
        
        
    def connExists(self, connId):
        return connId in self.all
        
        
    def getConnInfo(self, connId):
        return self.connIdToConnInfo[connId]
    
    
    def getConnAmount(self):
        return len(self.all)
        
        
    ##external functions - status
    
    def setSendable(self, sendable, connId):
        if sendable:
            assert not connId in self.sendable,'state out of sync!'
            self.sendable.add(connId)
            self.event.set()
        else:
            self.sendable.remove(connId)
            
            
    def setRecvable(self, recvable, connId):
        if recvable:
            assert not connId in self.recvable,'state out of sync!'
            self.recvable.add(connId)
            self.event.set()
        else:
            self.recvable.remove(connId)
            
            
    def setErrored(self, errored, connId):
        if errored:
            assert not connId in self.errored,'state out of sync!'
            self.errored.add(connId)
            self.event.set()
        else:
            self.errored.remove(connId)
            
            
    def getSendable(self, connId):
        return connId in self.sendable
    
    
    def getRecvable(self, connId):
        return connId in self.recvable
    
    
    def getErrored(self, connId):
        return connId in self.errored
    
    
    def select(self, recvInterest, sendInterest, errorInterest):
        recvable = recvInterest.intersection(self.recvable)
        sendable = sendInterest.intersection(self.sendable)
        errored = errorInterest.intersection(self.errored)
        errored.update(errorInterest.difference(self.all))
        return recvable, sendable, errored
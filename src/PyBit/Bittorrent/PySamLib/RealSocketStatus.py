"""
Copyright 2009  Blub

RealSocketStatus, a class which stores which async socket wants to recv, send, ...
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

class RealSocketStatus:
    def __init__(self):
        self._allConns = set()
        self._wantsToSend = set()
        self._wantsToRecv = set()
        self._allowedToSend = set()
        self._allowedToRecv = set()
        
        self.connIdToConnInfo = {}
        
        
    def addConn(self, connId, destId):
        self._allConns.add(connId)
        self._allowedToSend.add(connId)
        self._allowedToRecv.add(connId)
        
        self.connIdToConnInfo[connId] = destId
    
    
    def removeConn(self, connId):
        self._allConns.remove(connId)
        self._allowedToSend.discard(connId)
        self._allowedToRecv.discard(connId)
        self._wantsToSend.discard(connId)
        self._wantsToRecv.discard(connId)
        
        del self.connIdToConnInfo[connId]
        
        
    def connExists(self, connId):
        return connId in self._allConns
        
        
    def getConnInfo(self, connId):
        return self.connIdToConnInfo[connId]
        
    
    def setWantsToSend(self, want, connId):
        if want:
            assert not connId in self._wantsToSend,'state out of sync!'
            self._wantsToSend.add(connId)
        else:
            self._wantsToSend.remove(connId)
            
            
    def setWantsToRecv(self, want, connId):
        if want:
            assert not connId in self._wantsToRecv,'state out of sync!'
            self._wantsToRecv.add(connId)
        else:
            self._wantsToRecv.remove(connId)
            
    
    def setAllowedToSend(self, allowed, connId):
        if allowed:
            assert not connId in self._allowedToSend,'state out of sync!'
            self._allowedToSend.add(connId)
        else:
            self._allowedToSend.remove(connId)
            
            
    def setAllowedToRecv(self, allowed, connId):
        if allowed:
            assert not connId in self._allowedToRecv,'state out of sync!'
            self._allowedToRecv.add(connId)
        else:
            self._allowedToRecv.remove(connId)
        
    
    def getSelectSets(self):
        recv = self._wantsToRecv.intersection(self._allowedToRecv)
        send = self._wantsToSend.intersection(self._allowedToSend)
        error = self._allConns.copy()
        return recv, send, error
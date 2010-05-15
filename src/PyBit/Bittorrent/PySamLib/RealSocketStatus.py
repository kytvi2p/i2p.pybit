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


from AsyncPoll import AsyncPoll, POLLIN, POLLOUT, POLLERROR


class RealSocketStatus:
    def __init__(self, sockManager):
        self.pollObj = AsyncPoll(sockManager)
        self._allConns = set()
        self._wantsToSend = set()
        self._wantsToRecv = set()
        self.connIdToConnInfo = {}
        
        
    def _updateState(self, connId):
        state = POLLERROR
        if connId in self._wantsToSend:
            state |= POLLOUT
            
        if connId in self._wantsToRecv:
            state |= POLLIN
            
        self.pollObj.register(connId, state)
        
        
    def addConn(self, connId, destId):
        self._allConns.add(connId)
        self._updateState(connId)
        self.connIdToConnInfo[connId] = destId
    
    
    def removeConn(self, connId):
        self._allConns.remove(connId)
        self._wantsToSend.discard(connId)
        self._wantsToRecv.discard(connId)
        self.pollObj.unregister(connId)
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
        self._updateState(connId)
            
            
    def setWantsToRecv(self, want, connId):
        if want:
            assert not connId in self._wantsToRecv,'state out of sync!'
            self._wantsToRecv.add(connId)
        else:
            self._wantsToRecv.remove(connId)
        self._updateState(connId)
        
    
    def getConnEvents(self):
        return self.pollObj.poll(1000)

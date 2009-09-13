"""
Copyright 2009  Blub

ConnectionStatus, a class to keep track, which connections need to be checked for recving/sending/... .
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

class ConnectionStatus:
    def __init__(self):
        self._allConns = set()
        self._wantsToSend = set()
        self._wantsToRecv = set()
        self._allowedToSend = set()
        self._allowedToRecv = set()
        
        self.lock = threading.RLock()
        
        
    def addConn(self, connId):
        self.lock.acquire()
        self._allConns.add(connId)
        self._wantsToRecv.add(connId)
        self._allowedToSend.add(connId)
        self._allowedToRecv.add(connId)
        self.lock.release()
    
    
    def removeConn(self, connId):
        self.lock.acquire()
        self._allConns.remove(connId)
        self._allowedToSend.discard(connId)
        self._allowedToRecv.discard(connId)
        self._wantsToSend.discard(connId)
        self._wantsToRecv.discard(connId)
        self.lock.release()
        
    
    def wantsToSend(self, want, connId):
        self.lock.acquire()
        if want:
            assert not connId in self._wantsToSend,'state out of sync!'
            self._wantsToSend.add(connId)
        else:
            self._wantsToSend.remove(connId)
        self.lock.release()
            
            
    def wantsToRecv(self, want, connId):
        self.lock.acquire()
        if want:
            assert not connId in self._wantsToRecv,'state out of sync!'
            self._wantsToRecv.add(connId)
        else:
            self._wantsToRecv.remove(connId)
        self.lock.release()
            
    
    def allowedToSend(self, allowed, connId):
        self.lock.acquire()
        if allowed:
            assert not connId in self._allowedToSend,'state out of sync!'
            self._allowedToSend.add(connId)
        else:
            self._allowedToSend.remove(connId)
        self.lock.release()
            
            
    def allowedToRecv(self, allowed, connId):
        self.lock.acquire()
        if allowed:
            assert not connId in self._allowedToRecv,'state out of sync!'
            self._allowedToRecv.add(connId)
        else:
            self._allowedToRecv.remove(connId)
        self.lock.release()
        
    
    def getSelectSets(self):
        self.lock.acquire()
        recv = self._wantsToRecv.intersection(self._allowedToRecv)
        send = self._wantsToSend.intersection(self._allowedToSend)
        error = self._allConns.copy()
        self.lock.release()
        return recv, send, error

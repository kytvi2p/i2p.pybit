"""
Copyright 2009  Blub

AsyncSocket, a class which emulates the normal socket interface.
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


class AsyncSocketError(Exception):
    pass
            



class AsyncSocket:
    def __init__(self, sockManager, sockId=None, remoteAddr=None):
        self.sockManager = sockManager
        self.sockId = sockId
        self.remoteAddr = remoteAddr
    
    
    ##helpers##
    
    def fileno(self):
        if self.sockId is None:
            raise AsyncSocketError("No valid socket id")
        return self.sockId
    
    
    def getpeername(self):
        if self.remoteAddr is None:
            raise AsyncSocketError("No valid socket id")
        return self.remoteAddr
    
    
    ##data transfer, accepting conns, ...
        
    def connect(self, addr):
        self.sockId = self.sockManager.connect(addr)
        self.remoteAddr = addr
    
    
    def listen(self, addr):
        self.sockId = self.sockManager.listen(addr)
        
        
    def accept(self):
        if self.sockId is None:
            raise AsyncSocketError("No valid socket id")
        
        newConn = self.sockManager.accept(self.sockId)
        if newConn is None:
            raise AsyncSocketError("Would block")
        else:
            newConn = AsyncSocket(self.sockManager, newConn[0], newConn[1])
        return newConn
    
        
    def send(self, data):
        if self.sockId is None:
            raise AsyncSocketError("No valid socket id")
        return self.sockManager.send(self.sockId, data)
    
    
    def recv(self, max=4096):
        if self.sockId is None:
            raise AsyncSocketError("No valid socket id")
        return self.sockManager.recv(self.sockId, max)
    
    
    def close(self):
        if self.sockId is None:
            raise AsyncSocketError("No valid socket id")
        self.sockManager.close(self.sockId)

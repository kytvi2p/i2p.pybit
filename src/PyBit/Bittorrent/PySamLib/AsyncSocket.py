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


class AsyncSocketInvalidArgument(Exception):
    pass


class AsyncSocket:
    def __init__(self, asm, sockNum=None, remoteAddr=None):
        self.asm = asm
        self.sockNum = sockNum
        self.timeout = None
        self.remoteAddr = remoteAddr         

    
    def fileno(self):
        return self.sockNum
    
    
    def connect(self, addr, recvBufMaxSize=32768, sendBufMaxSize=32768):
        if self.sockNum is not None:
            raise AsyncSocketError("Already connected")
        self.sockNum = self.asm.connect(addr, recvBufMaxSize, sendBufMaxSize)


    def send(self, data):
        if self.sockNum is None:
            raise AsyncSocketError("Not connected")
            
        bytesSend = self.asm.send(self.sockNum, data)
        return bytesSend
    
    
    def recv(self, maxBytes=-1):
        if self.sockNum is None:
            raise AsyncSocketError("Not connected")
        
        data = self.asm.recv(self.sockNum, maxBytes)
        return data
        
    
    def close(self):
        if self.sockNum is None:
            raise AsyncSocketError("Not connected")
        
        self.asm.close(self.sockNum)
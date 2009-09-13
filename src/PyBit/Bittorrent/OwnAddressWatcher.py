"""
Copyright 2009  Blub

OwnAddressWatcher, a class which keeps track of our own i2p destination.
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

from time import sleep
import logging
import threading

class OwnAddressWatcher:
    def __init__(self, destNum, samSockManager):
        self.destNum = destNum
        self.samSockManager = samSockManager
        
        self.ownAddr = ''
        
        self.log = logging.getLogger("OwnAddressWatcher")
        self.lock = threading.RLock()
        
        
    ##internal functions - general
        
    def _checkAddr(self):
        addr = self.samSockManager.getOwnDestination(destNum=self.destNum, timeout=0)
        if addr is not None:
            if addr != self.ownAddr:
                self.log.debug("New address: %s", addr)
                self.ownAddr = addr
    
    
    ##external functions - other
    
    def getOwnAddr(self):
        self.lock.acquire()
        self._checkAddr()
        addr = self.ownAddr
        self.log.debug('Returning "%s" as own address', addr)
        self.lock.release()
        return addr
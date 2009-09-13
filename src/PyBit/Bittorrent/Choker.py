"""
Copyright 2009  Blub

Choker, a class which handles choking and unchoking connection to other bittorrent clients.
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

from random import choice
import logging
import threading

class Choker:
    def __init__(self, torrentIdent, eventScheduler, connHandler, ownStatus):
        self.torrentIdent = torrentIdent
        self.sched = eventScheduler
        self.connHandler = connHandler
        self.ownStatus = ownStatus
        
        self.chokeEventId = None
        self.log = logging.getLogger(torrentIdent+'-Choker')
        self.lock = threading.RLock()
        
    
    def _choke(self):
        self.log.info('Choking...')
        gotPieces = self.ownStatus.getGotPieces()
        
        conns = self.connHandler.getAllConnections(self.torrentIdent)
        shouldUpload = set()
        
        #get basic info
        uploadingConns = set()
        uploadableConns = set()
        
        for conn in conns:
            if not conn.localChoked():
                #uploading conn
                uploadingConns.add(conn)
                
            if conn.remoteInterested() and conn.getStatus().hasMatchingMissingPieces(gotPieces):
                #uploadable
                uploadableConns.add(conn)
        
        if len(uploadableConns) > 0:
            #pick one connection randomly (FIXME: better way to do this?)
            conn = choice(list(uploadableConns))
            self.log.debug('conn "%d": Picked this conn as the random upload target', conn.fileno())
            shouldUpload.add(conn)
            uploadableConns.remove(conn)
        
        #create list for comparing the others
        compareList = []
        for conn in uploadableConns:
            compareList.append((conn.localInterested(), conn.getScore(), conn))
            
        compareList.sort()
        compareList.reverse()
        
        for connSet in compareList:
            self.log.debug('conn "%d": Possible Upload candidate with local Interest "%d" and score "%f" (payload ratio "%f")',
                           connSet[2].fileno(), connSet[0], connSet[1], connSet[2].getPayloadRatio())
        
        #get needed conns
        for connSet in compareList[:4]:
            self.log.debug('conn "%d": Decided to upload to this peer', connSet[2].fileno())
            shouldUpload.add(connSet[2])

            
        #change choke status accordingly
        unchokeConns = shouldUpload.difference(uploadingConns)
        for conn in unchokeConns:
            self.log.debug('conn "%d": Unchoking', conn.fileno())
            conn.setLocalChoke(False)
        
        chokeConns = uploadingConns.difference(shouldUpload)
        for conn in chokeConns:
            self.log.debug('conn "%d": Choking', conn.fileno())
            conn.setLocalChoke(True)
            
        self.log.info('finished choking')
            
    
    def _start(self):
        if self.chokeEventId == None:
            self.chokeEventId = self.sched.scheduleEvent(self.choke, timedelta=60, repeatdelta=60)
        
            
    def _stop(self):
        self.sched.removeEvent(self.chokeEventId)
        self.chokeEventId = None
        
        
    def choke(self):
        self.lock.acquire()
        if self.chokeEventId is not None:
            self._choke()
        self.lock.release()
        
        
    def start(self):
        self.lock.acquire()
        self._start()
        self.lock.release()
        
    
    def stop(self):
        self.lock.acquire()
        self._stop()
        self.lock.release()
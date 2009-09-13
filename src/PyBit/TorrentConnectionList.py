"""
Copyright 2009  Blub

TorrentConnectionList, the class which creates the dialog, which shows the connections of the selected torrent.
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

import wx

from VirtualListCtrl import VirtualListCtrl

class TorrentConnectionList(VirtualListCtrl):
    def __init__(self, rawUpdateFunc, parent, **kwargs):
        self.torrentId = None
  
        #Syntax: NameOfColumn, NameOfStat, DataType, ColumnWidth
        cols = [('Addr','addr', 'native', 125),\
                ('Direction','direction','native', 75),\
                ('Connected', 'connectedInterval', 'timeInterval', 75),\
                ('Progress', 'peerProgress', 'percent', 75),\
                ('Downloaded', 'inPayloadBytes', 'dataAmount', 75),\
                ('DownSpeed', 'inRawSpeed', 'transferSpeed', 75),\
                ('Uploaded', 'outPayloadBytes', 'dataAmount', 75),\
                ('UpSpeed', 'outRawSpeed', 'transferSpeed', 75),\
                ('I', 'localInterest', 'bool', 20),\
                ('C', 'localChoke', 'bool', 20),\
                ('RI', 'remoteInterest', 'bool', 30),\
                ('RC', 'remoteChoke', 'bool', 30),\
                ('lReq', 'localRequestCount', 'int', 50),\
                ('rReq', 'remoteRequestCount', 'int', 50)]
       
        self.rawUpdateFunc = rawUpdateFunc
        self._updateStatKw()
        func = lambda: self.rawUpdateFunc(**self.statKw)['bt']['connections']
        VirtualListCtrl.__init__(self, cols, func, parent, **kwargs)
        
        
    def _updateStatKw(self):
        self.statKw = {'wantedStats':{'bt':self.torrentId},
                       'wantedTorrentStats':{'connections':True}}
        

    def changeTorrentId(self, torrentId):
        self.lock.acquire()
        if self.torrentId is not None and torrentId is None:
            #got disabled
            self.torrentId = None
            self.clear()
            
        elif self.torrentId is None and torrentId is not None:
            #got enabled
            self.torrentId = torrentId
            self._updateStatKw()
            self.dataUpdate()
            
        elif self.torrentId is not None and torrentId is not None:
            #normal change
            if not self.torrentId == torrentId:
                self.torrentId = torrentId
                self._updateStatKw()
                self.dataUpdate()
        self.lock.release()
        

    def manualUpdate(self):
        self.lock.acquire()
        if self.torrentId is not None:
            self.dataUpdate()
        self.lock.release()

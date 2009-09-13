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

from VirtualListCtrl import PersistentVirtualListCtrl

class TorrentConnectionList(PersistentVirtualListCtrl):
    def __init__(self, persister, version, rawUpdateFunc, parent, **kwargs):
        self.torrentId = None
  
        #Syntax: NameOfColumn, NameOfStat, DataType, ColumnWidth
        cols = [('Id','id', 'int', 40, False),\
                ('Addr','addr', 'native', 125, True),\
                ('Client','peerClient', 'native', 100, True),\
                ('Direction','direction','native', 75, True),\
                ('Connected', 'connectedInterval', 'timeInterval', 75, True),\
                ('Progress', 'peerProgress', 'percent', 75, True),\
                ('I', 'localInterest', 'bool', 20, True),\
                ('C', 'localChoke', 'bool', 20, True),\
                ('RI', 'remoteInterest', 'bool', 30, True),\
                ('RC', 'remoteChoke', 'bool', 30, True),\
                ('Downloaded (R)', 'inRawBytes', 'dataAmount', 110, False),\
                ('Downloaded (P)', 'inPayloadBytes', 'dataAmount', 110, True),\
                ('Downspeed (R)', 'inRawSpeed', 'transferSpeed', 110, True),\
                ('Uploaded (R)', 'outRawBytes', 'dataAmount', 100, False),\
                ('Uploaded (P)', 'outPayloadBytes', 'dataAmount', 100, True),\
                ('Upspeed (R)', 'outRawSpeed', 'transferSpeed', 100, True),\
                ('lReq', 'localRequestCount', 'int', 50, True),\
                ('rReq', 'remoteRequestCount', 'int', 50, True),\
                ('Avg. Downspeed (R)', 'avgInRawSpeed', 'transferSpeed', 140, False),\
                ('Avg. Downspeed (P)', 'avgInPayloadSpeed', 'transferSpeed', 140, False),\
                ('Avg. Upspeed (R)', 'avgOutRawSpeed', 'transferSpeed', 125, False),\
                ('Avg. Upspeed (P)', 'avgOutPayloadSpeed', 'transferSpeed', 125, False),\
                ('Score', 'score', 'float', 75, False),\
                ('Payload Ratio', 'payloadRatio', 'float', 125, False),
                ('Protocol Overhead', 'protocolOverhead', 'percent', 150, False),
                ('Offered Pieces', 'offeredPieces', 'native', 100, False)]
       
        self.rawUpdateFunc = rawUpdateFunc
        PersistentVirtualListCtrl.__init__(self, persister, 'TorrentConnectionList-', self._updatePerstData, version,
                                           cols, self._getRowData, parent, rowIdCol='Id', **kwargs)
       
        
    def _updatePerstData(self, persColData, currentVersion):
        return persColData
    
        
    def _getRowData(self):
        if self.torrentId is None:
            data = []
        else:
            statKw = {'wantedStats':{'bt':self.torrentId},
                      'wantedTorrentStats':{'connections':True}}
            data = self.rawUpdateFunc(**statKw)['bt']['connections']
        return data
        

    def changeTorrentId(self, torrentId):
        self.lock.acquire()
        if self.torrentId is not None and torrentId is None:
            #got disabled
            self.torrentId = None
            self.clear()
            
        elif self.torrentId is None and torrentId is not None:
            #got enabled
            self.torrentId = torrentId
            self.dataUpdate()
            
        elif self.torrentId is not None and torrentId is not None:
            #normal change
            if not self.torrentId == torrentId:
                self.torrentId = torrentId
                self.dataUpdate()
        self.lock.release()
        

    def manualUpdate(self):
        self.lock.acquire()
        if self.torrentId is not None:
            self.dataUpdate()
        self.lock.release()

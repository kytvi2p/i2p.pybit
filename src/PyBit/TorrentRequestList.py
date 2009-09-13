"""
Copyright 2009  Blub

TorrentRequestList, the class which creates the dialog, which shows the running requests of the selected torrent.
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

class TorrentRequestList(PersistentVirtualListCtrl):
    def __init__(self, persister, version, rawUpdateFunc, parent, **kwargs):
        self.torrentId = None
        
        #Syntax: NameOfColumn, NameOfStat, DataType, ColumnWidth
        cols = [('Piece', 'pieceIndex', 'int', 75, True),\
                ('Size', 'pieceSize', 'dataAmount', 75, False),\
                ('Priority', 'piecePriority', 'int', 75, True),\
                ('Availability', 'pieceAvailability', 'int', 75, True),\
                ('Chunks', 'totalRequests', 'int', 75, True),\
                ('Finished', 'finishedRequests', 'int', 75, True),\
                ('Needed', 'neededRequests', 'int', 75, False),\
                ('In Progress', 'runningRequests', 'int', 100, True),\
                ('F', 'filled', 'bool', 20, True),\
                ('Used Conns', 'assignedConnsNum', 'int', 100, True),\
                ('Used Conns (List)', 'assignedConnsList', 'native', 150, False)]
       
        self.rawUpdateFunc = rawUpdateFunc
        PersistentVirtualListCtrl.__init__(self, persister, 'TorrentRequestList-', self._updatePerstData, version,
                                           cols, self._getRowData, parent, rowIdCol='Piece', **kwargs)
       
        
    def _updatePerstData(self, persColData, currentVersion):
        return persColData
    
        
    def _getRowData(self):
        if self.torrentId is None:
            data = []
        else:
            statKw = {'wantedStats':{'bt':self.torrentId},
                      'wantedTorrentStats':{'requests':True}}
            data = self.rawUpdateFunc(**statKw)['bt']['requests']
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

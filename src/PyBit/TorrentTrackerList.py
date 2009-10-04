"""
Copyright 2009  Blub

TorrentTrackerList, the class which creates the dialog, which shows an overview of the trackers of the selected torrent.
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

class TorrentTrackerList(PersistentVirtualListCtrl):
    def __init__(self, persister, version, rawUpdateFunc, parent, **kwargs):
        self.torrentId = None
        
        #Syntax: NameOfColumn, NameOfStat, DataType, ColumnWidth
        cols = [('Id', 'trackerId', 'int', 75, False),\
                ('Tier', 'tier', 'int', 75, True),\
                ('Pos In Tier', 'tierPos', 'int', 75, True),\
                ('Url', 'trackerUrl', 'native', 700, True),\
                ('Seeds', 'seeds', 'int', 75, True),\
                ('Leeches', 'leeches', 'int', 75, True),\
                ('Downloads', 'downloads', 'int', 75, True)]
       
        self.rawUpdateFunc = rawUpdateFunc
        PersistentVirtualListCtrl.__init__(self, persister, 'TorrentTrackerList-', self._updatePerstData, version,
                                           cols, self._getRowData, parent, rowIdCol='Id', **kwargs)
       
        
    def _updatePerstData(self, persColData, currentVersion):
        return persColData
    
        
    def _getRowData(self):
        if self.torrentId is None:
            data = []
        else:
            statKw = {'wantedStats':{'bt':self.torrentId},
                      'wantedTorrentStats':{'tracker':True}}
            data = self.rawUpdateFunc(**statKw)['bt']['tracker']
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

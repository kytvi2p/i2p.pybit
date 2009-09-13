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

from SortableList import SortableList

class TorrentConnectionList(SortableList):
    def __init__(self, updateFunc, parent, **kwargs):
        self.torrentId = None
        
        def upFunc():
            if self.torrentId==None:
                return []
            else:
                return updateFunc(wantedStats={'bt':self.torrentId}, wantedTorrentStats={'connections':True})['bt']['connections']
            
        #Syntax: NameOfColumn, NameOfStat, DataType, ShouldWatch
        cols = [('Addr','addr', 'native', False, 125),\
                ('Direction','direction','native', False, 75),\
                ('Connected', 'connectedInterval', 'timeInterval', False, 75),\
                ('Progress', 'peerProgress', 'percent', False, 75),\
                ('Downloaded', 'inPayloadBytes', 'dataAmount', False, 75),\
                ('DownSpeed', 'inRawSpeed', 'transferSpeed', False, 75),\
                ('Uploaded', 'outPayloadBytes', 'dataAmount', False, 75),\
                ('UpSpeed', 'outRawSpeed', 'transferSpeed', False, 75),\
                ('I', 'localInterest', 'bool', False, 20),\
                ('C', 'localChoke', 'bool', False, 20),\
                ('RI', 'remoteInterest', 'bool', False, 30),\
                ('RC', 'remoteChoke', 'bool', False, 30),\
                ('lReq', 'localRequestCount', 'int', False, 50),\
                ('rReq', 'remoteRequestCount', 'int', False, 50)]
                
        SortableList.__init__(self, cols, upFunc, parent, **kwargs)
        

    def changeTorrentId(self, torrentId):
        self.lock.acquire()
        if not self.torrentId==torrentId:
            self.DeleteAllItems()
            self.torrentId = torrentId
            self.manualUpdate()
        self.lock.release()
        

    def manualUpdate(self):
        self.lock.acquire()
        self.dataUpdate()
        self.lock.release()

"""
Copyright 2009  Blub

TorrentStats, a class which shows various statistics for the currently selected torrent.
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

from InfoPanel import InfoPanel

class TorrentStats(InfoPanel):
    def __init__(self, rawUpdateFunc, parent, **kwargs):
        #items: *name*, *keyword*, *type*, *defaultvalue*, *columns*
        transfer = (('Downloaded:','inPayloadBytes','dataAmount',0, 1),\
                    ('Uploaded:','outPayloadBytes','dataAmount',0, 1),\
                    ('DownSpeed:','inRawSpeed','transferSpeed',0, 1),\
                    ('UpSpeed:','outRawSpeed','transferSpeed',0, 1),\
                    ('Avg DownSpeed:','avgInRawSpeed','transferSpeed',0, 1),\
                    ('Avg UpSpeed:','avgOutRawSpeed','transferSpeed',0, 1))
                    
                    
        torrent = (('Name:', 'torrentName', 'native', '', 2),\
                   ('Comment:', 'torrentComment', 'native', '', 2),\
                   ('Files:', 'fileAmount', 'int', 0, 1),\
                   ('Pieces:', 'pieceAmount', 'int', 0, 1),\
                   ('Size:', 'torrentSize', 'dataAmount', 0, 1),\
                   ('Size of a Piece:', 'pieceLength', 'dataAmount', 0, 1),\
                   ('Creator:', 'torrentCreator', 'native', '', 1),\
                   ('Creationdate:', 'torrentCreationDate', 'date', 0, 1),\
                   ('Trackers:', 'trackerAmount', 'int',0, 1))
                    
                    
        connections = (('Known Peers:', 'knownPeers', 'int', 0, 1),\
                       ('Connected Peers:', 'connectedPeers', 'int', 0, 1))
                    
        
        other = (('Name:', 'torrentName', 'native', '', 1),)
        
        #box: *name*, *colsPerRow*, *growableCols*, (*row*, *column*), (*rows*, *columns*), *items*
        content = (('Transfer', 4, (3,), (0,0), (1,1), transfer),\
                   ('Torrent', 4, (3,), (0,1), (1,1), torrent),\
                   ('Connections', 4, (3,), (1,0), (1,1), connections),\
                   ('Other', 4, (3,), (1,1), (1,1), other))
        
        self.rawUpdateFunc = rawUpdateFunc
        self.torrentId = None
        
        self._updateStatKw()
        func = lambda: self.rawUpdateFunc(**self.statKw)['bt']
        InfoPanel.__init__(self, func, content, (1,), (1,), parent, **kwargs)
        
        
    def _updateStatKw(self):
        self.statKw = {'wantedStats':{'bt':self.torrentId},
                       'wantedTorrentStats':{'peers':True,
                                             'torrent':True,
                                             'transfer':True,
                                             'transferAverages':True}}


    def changeTorrentId(self, torrentId):
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
                
                
    def manualUpdate(self):
        if self.torrentId is not None:
            self.dataUpdate()

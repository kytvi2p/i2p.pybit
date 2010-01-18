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
        #items: *name*, *keyword*, *type*, *defaultvalue*, *valueAlignment*, *columns*
        transfer = (('Downloaded (P/R):','inPayloadBytes','dataAmount',0,'R',1),\
                    ('','inRawBytes','dataAmount',0 ,'R', 1),\
                    ('Uploaded (P/R):','outPayloadBytes','dataAmount',0,'R',1),\
                    ('','outRawBytes','dataAmount',0,'R',1),\
                    ('Avg Downspeed (P/R):','avgInPayloadSpeed','transferSpeed',0,'R',1),\
                    ('','avgInRawSpeed','transferSpeed',0,'R',1),\
                    ('Avg Upspeed (P/R):','avgOutPayloadSpeed','transferSpeed',0,'R',1),\
                    ('','avgOutRawSpeed','transferSpeed',0,'R',1),\
                    ('Downspeed (R):','inRawSpeed','transferSpeed',0,'R',3),\
                    ('Upspeed (R):','outRawSpeed','transferSpeed',0,'R',3))
                    
                    
        torrent = (('Name:','torrentName','native','','L',2),\
                   ('Comment:','torrentComment','native','','L',2),\
                   ('Creator:','torrentCreator','native','','L',2),\
                   ('Creationdate:','torrentCreationDate','date',0,'R',1),\
                   ('Trackers:','trackerAmount','int',0,'R',1),\
                   ('Files:','fileAmount','int',0,'R',1),\
                   ('Pieces:','pieceAmount','int',0,'R',1),\
                   ('Size:','torrentSize','dataAmount',0,'R',1),\
                   ('Size of a Piece:','pieceLength','dataAmount',0,'R',1))
                    
                    
        connections = (('Leecher Per Seed:','knownLeechesPerSeed','float',0.0,'R',1),\
                       ('Data Sources:','peersWithLocalInterest','int',0,'R',1),\
                       ('Avg. Payload Ratio:','averagePeerPayloadRatio','float',0.0,'R',1),\
                       ('Avg. Progress:','averagePeerProgress','percent',0.0,'R',1))
        
        other = (('Name:','torrentName','native','','L',1),)
        
        #box: *name*, *colsPerRow*, *growableCols*, (*row*, *column*), (*rows*, *columns*), *items*
        content = (('Transfer', 4, (3,), (0,0), (1,1), transfer),\
                   ('Torrent', 4, (1,3), (0,1), (1,1), torrent),\
                   ('Connections', 4, (3,), (1,0), (1,1), connections),\
                   ('Other', 4, (3,), (1,1), (1,1), other))
        
        self.rawUpdateFunc = rawUpdateFunc
        self.torrentId = None
        
        self._updateStatKw()
        func = lambda: self.rawUpdateFunc(**self.statKw)['bt']
        InfoPanel.__init__(self, func, content, (1,), (1,), parent, **kwargs)
        
        
    def _updateStatKw(self):
        self.statKw = {'wantedStats':{'bt':self.torrentId},
                       'wantedTorrentStats':{'connectionAverages':True,
                                             'peers':True,
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

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
    def __init__(self, updateFunc, parent, **kwargs):
        transfer = (('Downloaded:','inPayloadBytes','dataAmount',0),\
                    ('Uploaded:','outPayloadBytes','dataAmount',0),\
                    ('DownSpeed:','inRawSpeed','transferSpeed',0),\
                    ('UpSpeed:','outRawSpeed','transferSpeed',0),\
                    ('Avg DownSpeed:','avgInRawSpeed','transferSpeed',0),\
                    ('Avg UpSpeed:','avgOutRawSpeed','transferSpeed',0))
                    
                    
        torrent = ( ('Size:','torrentSize', 'dataAmount',0),\
                    ('Name:','torrentName', 'native', ''),\
                    ('Trackers:', 'trackerAmount', 'int',0),\
                    ('Files:','fileAmount','int',0),\
                    ('Pieces:', 'pieceAmount','int',0),\
                    ('Size of a Piece:','pieceLength','dataAmount',0),\
                    ('Creator:','torrentCreator','native',''),\
                    ('Creationdate:','torrentCreationDate','date',0),\
                    ('Comment:','torrentComment','native',''))
                    
                    
        connections = (('Known Peers:','knownPeers','int',0),\
                       ('Connected Peers:','connectedPeers','int',0))
                    
        
        other = (('Name:','torrentName','native',''),)
        
        
        content = (('Transfer',transfer),\
                   ('Torrent',torrent),\
                   ('Connections',connections),\
                   ('Other',other))
        

        self.torrentId = None
        
        def upFunc():
            if self.torrentId==None:
                return None
            else:
                return updateFunc(wantedStats={'bt':self.torrentId}, wantedTorrentStats={'peers':True, 'torrent':True, 'transfer':True, 'transferAverages':True})['bt']
        
        InfoPanel.__init__(self, upFunc, content, 2, 2, parent, **kwargs)


    def changeTorrentId(self, torrentId):
        if not self.torrentId==torrentId:
            self.torrentId = torrentId
            self.manualUpdate()               

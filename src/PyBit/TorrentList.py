"""
Copyright 2009  Blub

TorrentList, the class which shows the main dialog, listing all added torrents and their status.
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

from __future__ import with_statement
import logging
import wx

from VirtualListCtrl import PersistentVirtualListCtrl
from Utilities import FunctionCallConverter


class TorrentList(PersistentVirtualListCtrl):
    def __init__(self, persister, version, torrentHandler, childWindow, updateFunc, parent, **kwargs):
        #data Stuff
        self.torrentHandler = torrentHandler
        self.childWindow = childWindow
        
        #logger
        self.log = logging.getLogger('TorrentList')
        
        #columns
        #Syntax: NameOfColumn, NameOfStat, DataType, ColumnWidth
        cols = [('Pos','pos', 'int', 40, True),\
                ('Id','id', 'int', 40, False),\
                ('Status', 'state', 'native', 75, True),\
                ('Name', 'torrentName', 'native', 125, True),\
                ('Size', 'torrentSize', 'dataAmount', 75, True),\
                ('Got', 'progressBytes', 'dataAmount', 75, True),\
                ('Progress', 'progressPercent', 'percent', 75, True),\
                ('Downloaded (R)', 'inRawBytes', 'dataAmount', 115, False),\
                ('Downloaded (P)', 'inPayloadBytes', 'dataAmount', 115, True),\
                ('Downspeed (R)', 'inRawSpeed', 'transferSpeed', 100, True),\
                ('Uploaded (R)', 'outRawBytes', 'dataAmount', 100, False),\
                ('Uploaded (P)', 'outPayloadBytes', 'dataAmount', 100, True),\
                ('Upspeed (R)', 'outRawSpeed', 'transferSpeed', 100, True),\
                ('Peers', ('connectedPeers', 'knownPeers') , 'peerStats', 125, True),\
                ('Avg. Downspeed (R)', 'avgInRawSpeed', 'transferSpeed', 140, False),\
                ('Avg. Downspeed (P)', 'avgInPayloadSpeed', 'transferSpeed', 140, False),\
                ('Avg. Upspeed (R)', 'avgOutRawSpeed', 'transferSpeed', 125, False),\
                ('Avg. Upspeed (P)', 'avgOutPayloadSpeed', 'transferSpeed', 125, False),\
                ('Protocol Overhead', 'protocolOverhead', 'percent', 150, False)]
               
        statKw = {'wantedStats':{'bt':'all'},
                  'wantedTorrentStats':{'peers':True,
                                        'queue':True,
                                        'progress':True,
                                        'torrent':True,
                                        'transfer':True,
                                        'transferAverages':True}}
                                        
        func = lambda: updateFunc(**statKw)['bt']
        PersistentVirtualListCtrl.__init__(self, persister, 'TorrentList-', self._updatePerstData, version,
                                           cols, func, parent, rowIdCol='Id', **kwargs)

        #events
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelect)
        
        
    def _updatePerstData(self, persColData, currentVersion):
        return persColData
    
        
    def manualUpdate(self):
        with self.lock:
            self.dataUpdate()
        

    def addTorrent(self, torrentFileData, savePath):
        #adds a fresh torrent
        with self.lock:
            #add Task to the handler
            self.torrentHandler.addTorrent(torrentFileData, savePath)
                
            #updates
            self.dataUpdate()
    

    def OnSelect(self, event):
        torrentId = self._getRawData('Id',self.GetFirstSelected())
        self.childWindow(torrentId)
        #event.Skip()
        
        
    def OnStart(self, event):
        #restart a stopped torrent
        with self.lock:
            #for each selected row tell the torrenthandler to restart the torrent
            for row in self._getSelectedRows():
                torrentId = self._getRawData('Id', row)
                self.torrentHandler.startTorrent(torrentId)
            #event.Skip()
            self.dataUpdate()
        

    def OnStop(self, event):
        #stops a running torrent
        with self.lock:
            #stop all selected torrents
            for row in self._getSelectedRows():
                torrentId = self._getRawData('Id', row)
                self.torrentHandler.stopTorrent(torrentId)                
            #event.Skip()
            self.dataUpdate()
            

    def OnRemove(self, event):
        #completly removes the torrent from the torrenthandler
        with self.lock:
            #find out which rows were selected
            selectedRows = self._getSelectedRows()
            selectedRows.reverse()

            #remove all selected rows from the list
            for row in selectedRows:
                torrentId = self._getRawData('Id', row)
                self.torrentHandler.removeTorrent(torrentId)

            self.childWindow(None)
            
            #event.Skip()
            self.dataUpdate()
        

    def OnUp(self, event):
        #moves all selected rows one up in the list
        with self.lock:
            #move all selected rows one up in the list
            for row in self._getSelectedRows():
                torrentId = self._getRawData('Id', row)
                self.torrentHandler.moveUp(torrentId)
            #event.Skip()
            self.dataUpdate()
        

    def OnDown(self, event):
        #moves all selected rows one up in the list
        with self.lock:
            #move all selected rows one up in the list
            for row in self._getSelectedRows():
                torrentId = self._getRawData('Id', row)
                self.torrentHandler.moveDown(torrentId)
            #event.Skip()
            self.dataUpdate()

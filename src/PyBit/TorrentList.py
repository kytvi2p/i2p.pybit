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

import logging
import wx

from SortableList import SortableList
from Utilities import FunctionCallConverter


class TorrentList(SortableList):
    def __init__(self, torrentHandler, childWindow, updateFunc, parent, **kwargs):
        #data Stuff
        self.torrentHandler = torrentHandler
        self.childWindow = childWindow
        
        #logger
        self.log = logging.getLogger('TorrentList')
        
        #columns
        #Syntax: NameOfColumn, NameOfStat, DataType, ShouldWatch, ColumnWidth
        cols = [('Pos','pos', 'int', False, 40),\
                ('Id','id', 'int', True, 40),\
                ('Status', 'state', 'str', False, 75),\
                ('Name', 'torrentName', 'str', False, 125),\
                ('Size', 'torrentSize', 'dataAmount', False, 75),\
                ('Got', 'progressBytes', 'dataAmount', False, 75),\
                ('Progress', 'progressPercent', 'percent', False, 75),\
                ('Downloaded', 'inPayloadBytes', 'dataAmount', False, 75),\
                ('DownSpeed', 'inRawSpeed', 'transferSpeed', False, 75),\
                ('Uploaded', 'outPayloadBytes', 'dataAmount', False, 75),\
                ('UpSpeed', 'outRawSpeed', 'transferSpeed', False, 75),\
                ('Peers', ('connectedPeers', 'knownPeers') , 'peerStats', False, 125)]
               
        statKw = {'wantedStats':{'bt':'all'},
                  'wantedTorrentStats':{'peers':True,
                                        'queue':True,
                                        'progress':True,
                                        'torrent':True,
                                        'transfer':True}}
                                        
        funcCaller = FunctionCallConverter(updateFunc, funcKw=statKw, resultFilter='bt', resultFilterFormat='item')
        SortableList.__init__(self, cols, funcCaller.callForValue, parent, **kwargs)

        #events
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelect)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnDeSelect)
        
        
    def _getSelectedRows(self):
        selectedRows = []
        selected = self.GetFirstSelected()
        while not selected==-1:
            selectedRows.append(selected)
            selected = self.GetNextSelected(selected)
        return selectedRows
        

    def manualUpdate(self):
        self.lock.acquire()
        self.dataUpdate()
        self.lock.release()
        

    def addTorrent(self, torrentFileData, savePath):
        #adds a fresh torrent
        self.lock.acquire()
        #add Task to the handler
        try:
            self.torrentHandler.addTorrent(torrentFileData, savePath)
            success = True
        except:
            success = False
            
        #updates
        self.dataUpdate()
        self.lock.release()
        return success
    

    def OnSelect(self, event):
        torrentId = self._getData('Id',self.GetFirstSelected())
        self.childWindow(torrentId)
        #event.Skip()
        

    def OnDeSelect(self, event):
        self.childWindow(None)
        #event.Skip()
        

    def OnStart(self, event):
        #restart a stopped torrent
        self.lock.acquire()
        
        #for each selected row tell the torrenthandler to restart the torrent
        for row in self._getSelectedRows():
            torrentId = self._getData('Id', row)
            self.torrentHandler.startTorrent(torrentId)
        #event.Skip()
        self.dataUpdate()
        self.lock.release()
        

    def OnStop(self, event):
        #stops a running torrent
        self.lock.acquire()

        #stop all selected torrents
        for row in self._getSelectedRows():
            torrentId = self._getData('Id', row)
            self.torrentHandler.stopTorrent(torrentId)                
        #event.Skip()
        self.dataUpdate()
        self.lock.release()

    def OnRemove(self, event):
        #completly removes the torrent from the torrenthandler
        self.lock.acquire()

        #find out which rows were selected
        selectedRows = self._getSelectedRows()
        selectedRows.reverse()

        #remove all selected rows from the list
        for row in selectedRows:
            torrentId = self._getData('Id', row)
            self.torrentHandler.removeTorrent(torrentId)

        self.childWindow(None)
        
        #event.Skip()
        self.dataUpdate()
        self.lock.release()
        

    def OnUp(self, event):
        #moves all selected rows one up in the list
        self.lock.acquire()

        #move all selected rows one up in the list
        for row in self._getSelectedRows():
            torrentId = self._getData('Id', row)
            self.torrentHandler.moveUp(torrentId)
        #event.Skip()
        self.dataUpdate()
        self.lock.release()
        

    def OnDown(self, event):
        #moves all selected rows one up in the list
        self.lock.acquire()
        
        #move all selected rows one up in the list
        for row in self._getSelectedRows():
            torrentId = self._getData('Id', row)
            self.torrentHandler.moveDown(torrentId)
        #event.Skip()
        self.dataUpdate()
        self.lock.release()

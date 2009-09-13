"""
Copyright 2009  Blub

StatusPanel, a class which manages multiple other dialogs.
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

class StatusPanel(wx.Notebook):
    def __init__(self, *args, **kwargs):
        wx.Notebook.__init__(self, *args, **kwargs)
        self.torrentId = None
        self.childNames = []
        self.childObjects = {}
        self.currentPage = 0        
        self.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnPageChange)
        

    def addChild(self, child, name):
        self.AddPage(child, name)        
        self.childNames.append(name)
        self.childObjects[name] = child
        

    def OnPageChange(self, event):       
        if self.torrentId is not None:            
            #disable old Page
            name = self.childNames[self.currentPage]
            self.childObjects[name].changeTorrentId(None)
            #enable new Page
            name = self.childNames[event.GetSelection()]
            self.childObjects[name].changeTorrentId(self.torrentId)
        self.currentPage = event.GetSelection()
        event.Skip()
        

    def changeTorrentId(self, torrentId):
        self.torrentId = torrentId
        name = self.childNames[self.currentPage]
        self.childObjects[name].changeTorrentId(self.torrentId)
        
        
    def manualUpdate(self):
        name = self.childNames[self.currentPage]
        self.childObjects[name].manualUpdate()

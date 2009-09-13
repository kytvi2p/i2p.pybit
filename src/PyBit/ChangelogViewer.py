"""
Copyright 2009  Blub

ChangelogViewer, a class which shows a scrollable dialog with the contents of the changelog file.
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
from ScrollableTextViewer import ScrollableTextViewer

class ChangelogViewer(wx.Frame):
    def __init__(self, parent, path, **kwargs):
        wx.Frame.__init__(self, parent, -1, 'Changelog', size=wx.Size(500, 400),\
                              style = wx.DEFAULT_FRAME_STYLE, **kwargs)
        self.CentreOnScreen()
        
        #display panel
        displayPanel = wx.Panel(self)
        vBox = wx.BoxSizer(wx.VERTICAL)
        
        #textbox
        self.textViewer = ScrollableTextViewer(displayPanel, file=path)
        vBox.Add(self.textViewer, 1, wx.EXPAND | wx.ALL, border = 2)

        #button
        buttonId = wx.NewId()
        button = wx.Button(displayPanel, buttonId, "Close")        
        vBox.Add(button, 0, flag = wx.ALIGN_CENTRE)
        
        displayPanel.SetSizer(vBox)

        #events
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=buttonId)

        #show panel
        self.Layout()
        self.Show()

    def OnClose(self, event):
        self.Destroy()
    
if __name__ == "__main__":
    app = wx.App()
    ChangelogViewer(None, u'todo')
    app.MainLoop()

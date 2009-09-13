"""
Copyright 2009  Blub

ScrollableTextViewerPanel and -Frame, two general classes for showing text or the contents of a file in a scrollable dialog.
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

from wx.lib.scrolledpanel import ScrolledPanel
import wx

class ScrollableTextViewerPanel(ScrolledPanel):
    def __init__(self, parent, text='', file=None, style=wx.SUNKEN_BORDER, **kwargs):
        
        ScrolledPanel.__init__(self, parent, style=style, **kwargs)
        vBox = wx.BoxSizer(wx.VERTICAL)
        if file is not None:
            try:
                fileObj = open(file, 'rb')
                text = fileObj.read()
                fileObj.close()
            except:
                text = ''

        #add text display
        self.textDisplay = wx.StaticText(self, -1, text)        
        vBox.Add(self.textDisplay, 1, wx.EXPAND | wx.ALL, border = 2)

        self.SetSizer(vBox)
        #  SetupScrolling(self, scroll_x, scroll_y, rate_x, rate_y, scrollToTop)
        self.SetupScrolling(rate_x=14, rate_y=14)
        self.Layout()
        

    def changeText(self, text='', file=None):
        if file is not None:
            try:
                fileObj = open(file, 'rb')
                text = fileObj.read()
                fileObj.close()
            except:
                text = ''

        self.textDisplay.SetLabel(text)
        self.SetupScrolling()
        



class ScrollableTextViewerFrame(wx.Frame):
    def __init__(self, parent, name, path, size=wx.Size(500, 400), **kwargs):
        wx.Frame.__init__(self, parent, -1, name, size=size,\
                              style = wx.DEFAULT_FRAME_STYLE, **kwargs)
        self.CentreOnScreen()
        
        #display panel
        displayPanel = wx.Panel(self)
        vBox = wx.BoxSizer(wx.VERTICAL)
        
        #textbox
        self.textViewer = ScrollableTextViewerPanel(displayPanel, file=path)
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
        
    
    def changeText(self, text='', file=None):
        self.textViewer.changeText(text, file)
        

    def OnClose(self, event):
        self.Destroy()
        
    
if __name__ == "__main__":
    app = wx.App()
    test = ScrollableTextViewerFrame(None, u'todo', u'todo')
    app.MainLoop()
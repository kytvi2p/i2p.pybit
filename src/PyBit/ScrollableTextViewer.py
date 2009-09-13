"""
Copyright 2009  Blub

ScrollableTextViewer, a general class for showing text or the contents of a file in a scrollable dialog.
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

class ScrollableTextViewer(wx.Panel):
    def __init__(self, parent, text='', file=None, style=wx.SUNKEN_BORDER, **kwargs):
        
        wx.Panel.__init__(self, parent, style=style, **kwargs)
        vBox = wx.BoxSizer(wx.VERTICAL)
        if file is not None:
            try:
                fileObj = open(file, 'rb')
                text = fileObj.read()
                fileObj.close()
            except:
                pass

        #set the scrolling stuff up
        self.scrollContainer = wx.ScrolledWindow(self)

        scrollBox = wx.BoxSizer(wx.VERTICAL)
        self.textDisplay = wx.StaticText(self.scrollContainer, -1, text)        
        scrollBox.Add(self.textDisplay, 1, wx.EXPAND | wx.ALL, border = 2)

        self.scrollContainer.SetAutoLayout(True)
        self.scrollContainer.SetSizer(scrollBox)
        self.scrollContainer.SetScrollRate(1, 1)

        #other stuff
        vBox.Add(self.scrollContainer, 1, wx.EXPAND | wx.ALL, border = 2)
        self.SetSizer(vBox)
        self.Layout()

    def changeText(self, text='', file=None):
        if file is not None:
            try:
                fileObj = open(file, 'rb')
                text = fileObj.read()
                fileObj.close()
            except:
                pass

        self.textDisplay.SetLabel(text)
        self.scrollContainer.FitInside()
        

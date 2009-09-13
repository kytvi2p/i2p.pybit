"""
Copyright 2009  Blub

StatusBar, a class which creates the statusbar of PyBit.
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
from Conversion import transferSpeedToString

class StatusBar(wx.StatusBar):
    def __init__(self, updateFunc, parent):
        wx.StatusBar.__init__(self, parent=parent, style=wx.ST_SIZEGRIP)
        
        self.updateFunc = updateFunc

        #initialise Statusbar
        self.SetFieldsCount(3)
        self.SetStatusText('', 0)
        self.SetStatusText('Down: 0.0 B/s', 1)
        self.SetStatusText('Up: 0.0 B/s', 2)
        self.SetStatusWidths([-1,100, 100])

    def manualUpdate(self):
        inRate, outRate = self.updateFunc()
        self.SetStatusText('Down: ' + transferSpeedToString(inRate), 1)
        self.SetStatusText('Up: ' + transferSpeedToString(outRate), 2)

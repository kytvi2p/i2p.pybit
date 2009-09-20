"""
Copyright 2009  Blub

About, a class which displays a simple dialog with basic information about PyBit.
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

class About(wx.Frame):
    def __init__(self, parent, GUIversion, **kwargs):
        wx.Frame.__init__(self, parent, -1, 'About', size=wx.Size(280, 210),\
                          style = wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP, **kwargs)
        self.CentreOnScreen()
        #stuff
        vBox = wx.BoxSizer(wx.VERTICAL)
        aboutPanel = AboutPanel(self, GUIversion)
        vBox.Add(aboutPanel, 1, wx.EXPAND | wx.ALL)
        
        self.SetSizer(vBox)
        self.Layout()
        self.Show()

class AboutPanel(wx.Panel):
    def __init__(self, parent, GUIversion, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        #stuff
        self.parent = parent
        vBox = wx.BoxSizer(wx.VERTICAL)

        #programName = wx.StaticText(self, -1, "Pybt")

        #vBox.Add(programName, 0)
        
        #about box
        aboutBox = wx.StaticBox(self, -1, "About")
        aboutSizer = wx.StaticBoxSizer(aboutBox, wx.VERTICAL)
        aboutText = wx.StaticText(self, -1, '\n'+\
                                  'Version:  '+GUIversion+'\n'+\
                                  '\n'+\
                                  'Author:   Blub\n'+\
                                  '\n'+\
                                  '\n'+\
                                  'The icons are part of (or derived from) the tango-icon-theme (see "http://tango.freedesktop.org/")')
        aboutSizer.Add(aboutText, 1, wx.EXPAND | wx.ALL, border = 2)
        vBox.Add(aboutSizer, 1, wx.EXPAND | wx.ALL, border = 2)

        buttonId = wx.NewId()
        button = wx.Button(self, buttonId, "Close")
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=buttonId)
        vBox.Add(button, 0, flag = wx.ALIGN_CENTRE)
        
        #Line everythign up
        self.SetSizer(vBox)
        self.Layout()

        
    def OnClose(self, event):
        self.parent.Destroy()

if __name__ == "__main__":
    app = wx.App()
    merk = About(None, '0.0.1')
    app.MainLoop()

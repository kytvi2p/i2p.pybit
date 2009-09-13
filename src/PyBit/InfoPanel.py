"""
Copyright 2009  Blub

InfoPanel, a general class for displaying data ordered by columns and rows in a dialog.
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

from copy import copy
import wx

import Conversion

class InfoPanel(wx.Panel):
    def __init__(self, updateFunc, content, colsPerRow, varsPerRow, parent, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        self.updateFunc = updateFunc
        self.data = {}
        self.dataToStringFuncs = copy(Conversion.dataToStringFuncs)
        
        
        mainSizer = wx.FlexGridSizer(cols = colsPerRow, vgap = 0, hgap = 0)
        for boxDef in content:            
            #create box
            box = wx.StaticBox(self, -1, boxDef[0])
            boxSizer = wx.StaticBoxSizer(box, wx.VERTICAL)
            boxItems = wx.FlexGridSizer(cols = varsPerRow*2, vgap = 3, hgap = 20)
            #add items
            boxDict = {}
            for itemDef in boxDef[1]:
                description = wx.StaticText(self, -1, itemDef[0])
                itemType = itemDef[2]
                value = wx.StaticText(self, -1, self.dataToStringFuncs[itemType](itemDef[3]))
                boxDict[itemDef[0]] = {'itemType':itemType,\
                                       'itemStatsName':itemDef[1],\
                                       'itemObject':value,\
                                       'itemDefaultValue':self.dataToStringFuncs[itemType](itemDef[3])}
                boxItems.Add(description, 0, wx.EXPAND | wx.ALL, border = 1)
                boxItems.Add(value, 0, wx.ALL, border = 1)

            for col in xrange(1,varsPerRow*2, 2):
                boxItems.AddGrowableCol(col,0)
            self.data[boxDef[0]]=boxDict              

            boxSizer.Add(boxItems, 1, wx.EXPAND | wx.ALL, border = 2)
            mainSizer.Add(boxSizer, 1, wx.EXPAND | wx.ALL, border = 2)
            
        #allow growing
        #for col in xrange(0, colsPerRow):
        mainSizer.AddGrowableCol(colsPerRow-1,1)
##        for row in xrange(1, ):
        mainSizer.AddGrowableRow((len(content)/colsPerRow)-1,1)
        #line everything up
        self.SetSizer(mainSizer)
        self.Layout()
        self.Show()
        
        
    def changeUpdateFunc(self, updateFunc):
        self.updateFunc = updateFunc
        

    def dataUpdate(self):
        stats = self.updateFunc()
        if stats is not None:
            for boxName in self.data.iterkeys():
                box = self.data[boxName]
                for itemName in box.iterkeys():
                    item = box[itemName]
                    data = stats[item['itemStatsName']]
                    item['itemObject'].SetLabel(self.dataToStringFuncs[item['itemType']](data))
                    self.Update()

        else:
            for boxName in self.data.keys():
                box = self.data[boxName]
                for itemName in box.keys():
                    item = box[itemName]
                    item['itemObject'].SetLabel(item['itemDefaultValue'])
                    self.Update()
        self.Layout()
        
        
    def clear(self):
        for boxName in self.data.keys():
            box = self.data[boxName]
            for itemName in box.keys():
                item = box[itemName]
                item['itemObject'].SetLabel(item['itemDefaultValue'])
                self.Update()
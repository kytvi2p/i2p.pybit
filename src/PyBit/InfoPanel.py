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
    def __init__(self, updateFunc, content, growableColumns, growableRows, parent, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        self.updateFunc = updateFunc
        self.items = []
        self.dataToStringFuncs = copy(Conversion.dataToStringFuncs)
        
        #box: *name*, *colsPerRow*, *growableCols*, (*row*, *column*), (*rows*, *columns*), *items*
        #items: *name*, *keyword*, *type*, *defaultvalue*, *valueAlignment*, *columns*
        
        mainSizer = wx.GridBagSizer(vgap = 0, hgap = 0)
        
        #create boxes
        for boxDef in content:            
            #create box
            box = wx.StaticBox(self, -1, boxDef[0])
            boxSizer = wx.StaticBoxSizer(box, wx.VERTICAL)
            boxItemGroups = wx.BoxSizer(wx.VERTICAL)
            boxItems = wx.GridBagSizer(vgap = 3, hgap = 20)
            boxItemsSizer = [boxItems]
            
            #add items
            curItemRow = 0
            curItemCol = 0
            curPerItemCol = 0
            maxItemCol = boxDef[1]
            
            for itemDef in boxDef[5]:
                #create name and value GUI items
                name = wx.StaticText(self, -1, itemDef[0])
                value = wx.StaticText(self, -1, self.dataToStringFuncs[itemDef[2]](itemDef[3]))
                
                #add it to the dict
                self.items.append({'itemType':itemDef[2],\
                                   'itemDataKeyword':itemDef[1],\
                                   'itemObject':value,\
                                   'itemDefaultValue':self.dataToStringFuncs[itemDef[2]](itemDef[3])})
                                    
                #check if there is still place in this row
                if curItemCol + itemDef[5] + 1 > maxItemCol:
                    #no more place
                    curItemCol = 0
                    
                    if itemDef[5] == curPerItemCol:
                        #still everything the same, just use a new row
                        curItemRow += 1
                    else:
                        #different number of cols per item, time for a new sizer
                        boxItemGroups.Add(boxItems, 0, wx.EXPAND | wx.BOTTOM, border = 3)
                        boxItems = wx.GridBagSizer(vgap = 3, hgap = 20)
                        boxItemsSizer.append(boxItems)
                        curItemRow = 0
                        
                #check alignment
                if itemDef[4] == 'L':
                    alignment = wx.ALIGN_LEFT
                else:
                    alignment = wx.ALIGN_RIGHT
                
                #add item to the GUI
                boxItems.Add(name, (curItemRow, curItemCol), (1,1), wx.FIXED_MINSIZE | wx.ALL, border = 0)
                boxItems.Add(value, (curItemRow, curItemCol+1), (1, itemDef[5]), alignment | wx.ALL, border = 0)
                
                #increment col, set curPerItemCol
                curItemCol += itemDef[5] + 1
                curPerItemCol = itemDef[5]
                
                
            #set growable cols
            for sizer in boxItemsSizer:
                for col in boxDef[2]:
                    sizer.AddGrowableCol(col, 1)
            
            #add box to the GUI
            boxItemGroups.Add(boxItems, 0, wx.EXPAND | wx.ALL, border = 0)
            boxSizer.Add(boxItemGroups, 1, wx.EXPAND | wx.ALL, border = 2)
            mainSizer.Add(boxSizer, boxDef[3], boxDef[4], wx.EXPAND | wx.ALL, border = 2)
            
            
        #set growable cols
        for col in growableColumns:
            mainSizer.AddGrowableCol(col, 1)
            
        #set growable rows
        for row in growableRows:
            mainSizer.AddGrowableRow(row, 1)
            
        #line everything up
        self.SetSizer(mainSizer)
        self.Layout()
        self.Show()
        
        
    def changeUpdateFunc(self, updateFunc):
        self.updateFunc = updateFunc
        

    def dataUpdate(self):
        data = self.updateFunc()
        if data is not None:
            for item in self.items:
                itemData = data[item['itemDataKeyword']]
                item['itemObject'].SetLabel(self.dataToStringFuncs[item['itemType']](itemData))
                self.Update()

        else:
            for item in self.items:
                item['itemObject'].SetLabel(item['itemDefaultValue'])
                self.Update()
        self.Layout()
        
        
    def clear(self):
        for box in self.data.itervalues():
            for item in box.itervalues():
                item['itemObject'].SetLabel(item['itemDefaultValue'])
                self.Update()
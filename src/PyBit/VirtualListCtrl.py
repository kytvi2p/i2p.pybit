"""
Copyright 2009  Blub

VirtualListCtrl, a general class which creates a dialog which represents a table with
(user selectable) columns and rows, sortable by column.
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
import sys
import threading
import wx

import Conversion


class VirtualListCtrl(wx.ListCtrl):
    def __init__(self, cols, dataFunc, parent, customDataToStringFuncs=[], rowIdCol=None, allowSort=True, defaultSortCol='', defaultSortDirection='ASC', id=-1,
                 pos=wx.DefaultPosition, size=wx.DefaultSize, style=wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_VRULES | wx.CLIP_CHILDREN, **kwargs):
        wx.ListCtrl.__init__(self, parent, id, pos, size, style, **kwargs)
        """
        cols:
            [(*columnName*, *dataKeyword*, *dataType*, *columnWidth*), ...]
        """
        self.dataFunc = dataFunc
        
        #get a copy of the converter dicts
        self.dataToStringFuncs = copy(Conversion.dataToStringFuncs)
        
        #add custom funcs
        for funcTup in customDataToStringFuncs:
            if not funcTup[0] in self.dataToStringFuncs:
                self.dataToStringFuncs[funcTup[0]]=funcTup[1]
        
        #image stuff
        self.imageList, self.images = self._createColSortImages()
        self.SetImageList(self.imageList, wx.IMAGE_LIST_SMALL)
                
        #columns
        self.rowIdCol = rowIdCol
        self.defaultSortCol = defaultSortCol
        self.defaultSortDirection = defaultSortDirection
        self.colDefaults = cols #default column data (size and so on)
        self._initColumns(cols) #sets class vars!
        
        #lock
        self.lock = threading.RLock() #guess...
        
        #events
        if allowSort:
            self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick, self) #sort on col click
        self.Bind(wx.EVT_LIST_COL_RIGHT_CLICK, self.OnColRightClick, self) #display options on right click on col
        self.Bind(wx.EVT_LIST_COL_END_DRAG, self.OnColResize, self) #update the size info for the resized column
        
        #tell ListCtrl how many items we currently have
        self.SetItemCount(0)
        
    
    ##internal functions - images
    
    def _createColSortImages(self):
        imageList = wx.ImageList(18, 18, mask=True)
        images = {}
        for imageName, imageIdent in (('arrowUp', wx.ART_GO_UP), ('arrowDown', wx.ART_GO_DOWN)):
            #add one image to the list
            orgImg = wx.ArtProvider_GetBitmap(imageIdent, wx.ART_OTHER, (14,14)).ConvertToImage()
            if (not isinstance(orgImg, type(wx.NullBitmap))) and sys.platform[:5] == 'linux' and orgImg.HasAlpha():
                #looks ok, init empty new image
                newImg = wx.EmptyImage(14, 18, clear=True)
                newImg.InitAlpha()
                for x in xrange(0, 14):
                    for y in xrange(0, 18):
                        newImg.SetAlpha(x, y, 0)
                        
                #copy original image into new one
                newImg.Paste(orgImg, 0, 3)
                if orgImg.HasAlpha():
                    for x in xrange(0, 14):
                        for y in xrange(0, 14):
                            newImg.SetAlpha(x, y+3, orgImg.GetAlpha(x, y))
                
            else:
                #this looks borked (Windows?), draw bitmap from scratch
                orgImg = wx.EmptyBitmap(9, 9)
                memDc = wx.MemoryDC()
                memDc.SelectObject(orgImg)
                
                #draw background
                memDc.SetPen(wx.Pen('WHITE', 1))
                memDc.SetBrush(wx.Brush('WHITE', wx.SOLID))
                memDc.DrawRectangle(0, 0, 9, 9)
                
                #draw triangle
                memDc.SetPen(wx.Pen('BLACK', 1))
                memDc.SetBrush(wx.Brush('BLACK', wx.SOLID))
                if imageIdent is wx.ART_GO_UP:
                    memDc.DrawPolygon(((0,8), (8,8), (4,0)))
                elif imageIdent is wx.ART_GO_DOWN:
                    memDc.DrawPolygon(((0,0), (8,0), (4,8)))
                    
                memDc.SelectObject(wx.NullBitmap)
                
                #convert to image, apply alpha
                newImg = orgImg.ConvertToImage()
                newImg.InitAlpha()
                for x in xrange(0, 9):
                    for y in xrange(0, 9):
                        if newImg.GetGreen(x, y) == 0:
                            #black
                            newImg.SetAlpha(x, y, 95)
                        else:
                            #white
                            newImg.SetAlpha(x, y, 0)
                
            
            #finally convert back to bitmap and store in dict
            images[imageName] = imageList.Add(newImg.ConvertToBitmap())
            
        return imageList, images
    
    
    def _applyColSortImages(self, sortColumn, sortDirection):
        self.ClearColumnImage(self.sortColumn)
        if sortDirection == 'ASC':
            self.SetColumnImage(sortColumn, self.images['arrowDown'])
        else:
            self.SetColumnImage(sortColumn, self.images['arrowUp'])
            
    
    ##internal functions - columns
    
    def _createColumnInfo(self, cols):
        #cols = [(*columnName*, *dataKeyword*, *dataType*, *columnWidth*, *active*), ...]
        
        colInfo = {}   #columns info stuff
        colMapper = [] #maps a column name to a position
        
        #build up mapper and info dict
        place = 0
        while place < len(cols):
            #process one col
            colSet = cols[place]
            colInfo[colSet[0]] = {'dataKeyword':colSet[1],
                                  'dataType':colSet[2],
                                  'columnWidth':colSet[3]}
            if colSet[4]:
                #active column
                colMapper.append(colSet[0])
            place += 1
        return colInfo, colMapper
    
    
    def _applyColumnInfo(self, colInfo, colMapper):
        #create the 'real' (=gui) columns
        for i in xrange(0, len(colMapper)):
            colName = colMapper[i]
            self.InsertColumn(i, colName)
            self.SetColumnWidth(i, colInfo[colName]['columnWidth'])
            
            
    def _createColumns(self, colInfo, colMapper):
        #create the columns itself
        self._applyColumnInfo(colInfo, colMapper)
        
        #set class vars
        self.colInfo = colInfo            #column info
        self.colMapper = colMapper        #maps a column name to a position
        self.colNum = len(self.colMapper) #number of columns
        self.colData = dict(((colName, []) for colName in self.colInfo)) #row data, per column one list
        
        
    def _initColumns(self, cols):
        #initialises everything columns related
        colInfo, colMapper = self._createColumnInfo(cols)
        self._createColumns(colInfo, colMapper)
        
        #index of the column, which is used for sorting
        if self.defaultSortCol in colMapper:
            self.sortColumn = colMapper.index(self.defaultSortCol)
        else:
            self.sortColumn = 0
        self.sortDirection = self.defaultSortDirection #sort direction, either ASC or DESC
        self._applyColSortImages(self.sortColumn, self.sortDirection)
        
        
    def _resetColumns(self):
        #reset everything back to the defaults
        self.DeleteAllColumns()                                         #remove all existing columns
        colInfo, colMapper = self._createColumnInfo(self.colDefaults)   #build the needed vars out of the defaults
        self._createColumns(colInfo, colMapper)                         #create new columns according to these default
        
        #index of the column, which is used for sorting
        if self.defaultSortCol in colMapper:
            self.sortColumn = colMapper.index(self.defaultSortCol)        
        else:
            self.sortColumn = 0
        self.sortDirection = self.defaultSortDirection #sort direction, either ASC or DESC
        self._applyColSortImages(self.sortColumn, self.sortDirection)
        self.dataUpdate() #refill the columns
        
        
    ##internal functions - data
        
    def _dataUpdate(self, data):
        oldDataAmount = len(self.colData[self.colMapper[0]])
        
        #remember selected rows if possible
        if self.rowIdCol is not None:
            rowIdColData = self.colData[self.rowIdCol]
            selectedRows = self._getSelectedRows()
            selectedRowIds = [rowIdColData[rowIdx] for rowIdx in selectedRows if rowIdx < len(rowIdColData)]
            for rowIdx in selectedRows:
                self.Select(rowIdx, on=0)
        
        #create sort list
        colName = self.colMapper[self.sortColumn]
        dataKeyword = self.colInfo[colName]['dataKeyword']
        if type(dataKeyword)==str:
            #single item
            sortList = (row[dataKeyword] for row in data)
        else:
            #multiple items
            sortList = []
            for row in data:
                sortList.append([row[singleDataKeyword] for singleDataKeyword in dataKeyword])
        
        #add row index
        sortList = map(lambda tup: (tup[1], tup[0]), enumerate(sortList))
        
        #sort the list
        sortList.sort(reverse=(self.sortDirection == 'DESC'))
            
        #create new data list
        for colName in self.colData.keys():
            #fill one column
            colDataKeyword = self.colInfo[colName]['dataKeyword']
            if type(colDataKeyword)==str:
                #only a single data item
                self.colData[colName] = [data[rowNum][colDataKeyword] for rowData, rowNum in sortList]
                
            else:
                #multiple data items
                colData = []
                for rowData, rowNum in sortList:
                    colData.append([data[rowNum][singleDataKeyword] for singleDataKeyword in colDataKeyword])
                self.colData[colName] = colData
                
        #set new item length if rows got added or removed
        newDataAmount = len(sortList)
        if newDataAmount != oldDataAmount:
            self.SetItemCount(newDataAmount)
            
        #restore row selection if possible
        if self.rowIdCol is not None:
            rowIdColData = self.colData[self.rowIdCol]
            selectedRows = [rowIdColData.index(rowId) for rowId in selectedRowIds if rowId in rowIdColData]
            for rowIdx in sorted(selectedRows):
                self.Select(rowIdx, on=1)
                
        #refresh currently displayed items
        firstDisplayedRow = self.GetTopItem()
        lastDisplayedRow = min(firstDisplayedRow + self.GetCountPerPage(), newDataAmount)
        self.RefreshItems(firstDisplayedRow, lastDisplayedRow)
        
        #windows is a bit strange and requires this call (the "RefreshItems" call should do the same ...)
        if sys.platform[:3] == 'win':
            if newDataAmount >= oldDataAmount:
                self.Refresh(False)
            else:
                self.Refresh(True)
                
    
    ##internal functions - columns

    def _disableCol(self, colName):
        if self.colNum > 1:
            #ok to disable column, its not the last one
            colPos = self.colMapper.index(colName)
            del self.colMapper[colPos]
            self.colNum -= 1
            self.DeleteColumn(colPos)

            #clean the whole sorting stuff up
            if self.sortColumn == colPos:
                #we deleted the row which is used for sorting, default back to the first col
                self.sortColumn = 0
                self.sortDirection = 'ASC'
                self._applyColSortImages(self.sortColumn, self.sortDirection)
                
            elif self.sortColumn > colPos:
                #we sort depending on a column which is after the deleted column
                self.sortColumn -= 1
        
        self.Refresh()
        

    def _enableCol(self, colName, colPos):
        if colPos is None:
            colPos = self.colNum
            
        #add col
        self.InsertColumn(colPos, colName)
        self.SetColumnWidth(colPos, self.colInfo[colName]['columnWidth'])
        self.colMapper.insert(colPos, colName)
        self.colNum += 1
        
        #cleanup sorting
        if self.sortColumn >= colPos:
            #we added a row before or at the position of the sorting column
            self.sortColumn += 1
            
        self.dataUpdate()
        
        
    def _moveCol(self, colName, direction):
        colPos = self.colMapper.index(colName)
        if (colPos + direction) >= 0 and (colPos + direction) < self.colNum:
            self.DeleteColumn(colPos)
            self.InsertColumn(colPos + direction, colName)
            self.SetColumnWidth(colPos + direction, self.colInfo[colName]['columnWidth'])
            del self.colMapper[colPos]
            self.colMapper.insert(colPos + direction, colName)

            #clean the whole sorting stuff up
            if direction < 0 and self.sortColumn < colPos and self.sortColumn >= colPos+direction:                
                self.sortColumn += 1
                
            elif direction > 0 and self.sortColumn > colPos and self.sortColumn <= colPos+direction:
                self.sortColumn -= 1
                
            elif self.sortColumn == colPos:
                self.sortColumn += direction
                
        self.dataUpdate()
        
        
    ##internal functions - events

    def _onColClick(self, event):
        clickedCol = event.GetColumn()
        if not clickedCol == self.sortColumn:
            #use another column for sorting stuff
            self._applyColSortImages(clickedCol, 'ASC')
            self.sortColumn = clickedCol
            self.sortDirection = 'ASC'
        else:
            #just reverse sorting order
            if self.sortDirection == 'ASC':
                self._applyColSortImages(self.sortColumn, 'DESC')
                self.sortDirection = 'DESC'
            else:
                self._applyColSortImages(self.sortColumn, 'ASC')
                self.sortDirection = 'ASC'
        
        self.dataUpdate()
        
        
    def _onColRightClick(self, event):
        cols = []
        for colName in self.colData.iterkeys():
            active = (colName in self.colMapper)
            cols.append((colName, active))
        cols.sort()
        
        clickedCol = event.GetColumn()
        if clickedCol == -1:
            merk = ColumnSelectionPopup(cols, self, None, None, None)
        else:
            merk = ColumnSelectionPopup(cols, self, self.colMapper[clickedCol], clickedCol, len(self.colMapper))
        self.PopupMenu(merk)
        
        
    def _onColResize(self, event):
        resizedColNum = event.GetColumn()
        resizedColName = self.colMapper[resizedColNum]
        newSize = self.GetColumnWidth(resizedColNum)
        self.colInfo[resizedColName]['columnWidth'] = newSize
                
    
    ##internal functions - other
    
    def _getRowCount(self):
        return len(self.colData[self.colMapper[0]])
        
    def _getRawData(self, colName, rowIndex):
        return self.colData[colName][rowIndex]
    
    
    def _getSelectedRows(self):
        selectedRows = []
        selected = self.GetFirstSelected()
        while not selected==-1:
            selectedRows.append(selected)
            selected = self.GetNextSelected(selected)
        return selectedRows
    
        
    ##external functions - data
    
    def getRawData(self, colName, rowIndex):
        self.lock.acquire()
        data = self._getRawData(colName, rowIndex)
        self.lock.release()
        return data
    
    
    def getSelectedRows(self):
        self.lock.acquire()
        rows = self._getSelectedRows()
        self.lock.release()
        return rows
    
    
    def clear(self):
        self.lock.acquire()
        self._dataUpdate([])
        self.lock.release()
        
    
    def dataUpdate(self):
        self.lock.acquire()
        data = self.dataFunc()
        self._dataUpdate(data)
        self.lock.release()
    
    
    ##external functions - columns

    def disableCol(self, colName):
        self.lock.acquire()
        self._disableCol(colName)
        self.lock.release()
        

    def enableCol(self, colName, colPos=None):
        self.lock.acquire()
        self._enableCol(colName, colPos)
        self.lock.release()
        

    def moveCol(self, colName, direction):
        self.lock.acquire()
        self._moveCol(colName, direction)
        self.lock.release()
        
        
    def resetCols(self):
        self.lock.acquire()
        self._resetColumns()
        self.lock.release()
         
    
    ##external functions - events

    def OnColClick(self, event):
        self.lock.acquire()
        self._onColClick(event)
        self.lock.release()
        
        
    def OnColRightClick(self, event):
        self.lock.acquire()
        self._onColRightClick(event)
        self.lock.release()
        
        
    def OnColResize(self, event):
        self.lock.acquire()
        self._onColResize(event)
        self.lock.release()
        
        
    def OnGetItemText(self, rowIndex, columnIndex):
        self.lock.acquire()
        if columnIndex >= self.colNum or rowIndex >= len(self.colData[self.colMapper[0]]):
            data = ''
        else:
            colName = self.colMapper[columnIndex]
            data = self.colData[colName][rowIndex]
            if data is None:
                data = ''
            else:
                data = self.dataToStringFuncs[self.colInfo[colName]['dataType']](data)
        self.lock.release()
        return data




class ColumnSelectionPopup(wx.Menu):
    def __init__(self, cols, parentDiag, clickedCol, clickedColNum, maxColNum, *args, **kwargs):
        wx.Menu.__init__(self, *args, **kwargs)
        #static
        self.parentDiag = parentDiag
        self.clickedCol = clickedCol
        self.clickedColNum = clickedColNum
        self.maxColNum = maxColNum
        
        id = wx.NewId()
        self.Append(id, 'Reset to defaults', 'Restore the default column ordering and size')
        self.Bind(wx.EVT_MENU, self.OnColumnReset, id=id)
        self.AppendSeparator()

        if clickedCol is not None:
            #move funcs
            id = wx.NewId()
            self.Append(id, 'Move to left', 'Moves column one step to the left')
            self.Bind(wx.EVT_MENU, self.OnMoveToLeft, id=id)
            
            id = wx.NewId()
            self.Append(id, 'Move x steps', 'Moves column x steps')
            self.Bind(wx.EVT_MENU, self.OnMoveToX, id=id)
            
            id = wx.NewId()
            self.Append(id, 'Move to right', 'Moves column one step to the right')
            self.Bind(wx.EVT_MENU, self.OnMoveToRight, id=id)

            self.AppendSeparator()
        
        #enable/disable columns
        self.idMapper = {}
        for tup in cols:
            id = wx.NewId()
            m = self.AppendCheckItem(id, tup[0], 'Activates or deactivates this column')
            #m.SetCheckable(True)
            if tup[1]==True:
                m.Toggle()
            self.idMapper[id]=tup[0]
            
            #event
            self.Bind(wx.EVT_MENU, self.OnClick, id=id)
            
        

    def OnClick(self, event):
        colName = self.idMapper[event.GetId()]
        if event.IsChecked() == True:
            if self.clickedColNum is not None:
                self.parentDiag.enableCol(colName, colPos=self.clickedColNum + 1)
            else:
                self.parentDiag.enableCol(colName, colPos=None)
        else:
            self.parentDiag.disableCol(colName)
        #event.Skip(False)
        

    def OnMoveToLeft(self, event):
        self.parentDiag.moveCol(self.clickedCol, -1)
        
        
    def OnMoveToX(self, event):
        min = self.clickedColNum * -1
        max = self.maxColNum - self.clickedColNum - 1
        diag = wx.NumberEntryDialog(self.parentDiag, 'How many steps should the column be moved?', 'Steps (left = -, right = +):', 'Move Column', 0, min, max)
        if diag.ShowModal() == wx.ID_OK:
            self.parentDiag.moveCol(self.clickedCol, diag.GetValue())
        

    def OnMoveToRight(self, event):
        self.parentDiag.moveCol(self.clickedCol, 1)
        
    
    def OnColumnReset(self, event):
        self.parentDiag.resetCols()
        
        
        

class PersistentVirtualListCtrl(VirtualListCtrl):
    def __init__(self, persister, persistPrefix, updateFunc, currentVersion, cols, dataFunc, parent, customDataToStringFuncs=[], rowIdCol=None, allowSort=True, defaultSortCol='', defaultSortDirection='ASC',
                 id=-1, pos=wx.DefaultPosition, size=wx.DefaultSize, style=wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_VRULES, **kwargs):
        self.persister = persister
        self.persistKey = persistPrefix + 'columnInfo'
        self.updateFunc = updateFunc
        self.currentVersion = currentVersion
        
        VirtualListCtrl.__init__(self, cols, dataFunc, parent, customDataToStringFuncs, rowIdCol, allowSort=allowSort, defaultSortCol=defaultSortCol, defaultSortDirection=defaultSortDirection, id=id, pos=pos, size=size, style=style, **kwargs)
        
        
    ##internal funcs - persisting
        
    def _initColumns(self, cols):
        #initialises everything columns related
        persColData = self.persister.get(self.persistKey, None)
        if persColData is None:
            #nothing persisted exists
            colInfo, colMapper = self._createColumnInfo(cols)
            self.sortDirection = self.defaultSortDirection
            if self.defaultSortCol in colMapper:
                self.sortColumn = colMapper.index(self.defaultSortCol)        
            else:
                self.sortColumn = 0
        else:
            #managed to get persisted data, update
            persColData = self.updateFunc(persColData, self.currentVersion)
            
            #restore
            colInfo = persColData['colInfo']
            colMapper = persColData['colMapper']
            self.sortColumn = persColData['sortColumn']
            self.sortDirection = persColData['sortDirection']
            
            #check for new and changed cols
            for colSet in cols:
                if colSet[0] not in colInfo:
                    #new, add it
                    colInfo[colSet[0]] = {'dataKeyword':colSet[1],
                                          'dataType':colSet[2],
                                          'columnWidth':colSet[3]}
                
                else:
                    #old, update dataKeyword and dataType in case anything changed
                    colInfo[colSet[0]]['dataKeyword'] = colSet[1]
                    colInfo[colSet[0]]['dataType'] = colSet[2]
                    
            
            
        self._createColumns(colInfo, colMapper)
        self._applyColSortImages(self.sortColumn, self.sortDirection)
        
        
    def _persist(self):
        persColData = {'colInfo':self.colInfo,
                       'colMapper':self.colMapper,
                       'sortColumn':self.sortColumn,
                       'sortDirection':self.sortDirection,
                       'version':self.currentVersion}
        self.persister.store(self.persistKey, persColData)
        
        
    ##internal funcs - other
    
    def _resetColumns(self):
        VirtualListCtrl._resetColumns(self)
        self._persist()
        

    def _onColClick(self, event):
        VirtualListCtrl._onColClick(self, event)
        self._persist()
        
        
    def _onColResize(self, event):
        VirtualListCtrl._onColResize(self, event)
        self._persist()
        
        
    def _disableCol(self, colName):
        VirtualListCtrl._disableCol(self, colName)
        self._persist()
        

    def _enableCol(self, colName, colPos):
        VirtualListCtrl._enableCol(self, colName, colPos)
        self._persist()
        

    def _moveCol(self, colName, direction):
        VirtualListCtrl._moveCol(self, colName, direction)
        self._persist()
"""
Copyright 2009  Blub

Torrent, a class which parses a torrent file and processes its information.
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

from Bencoding import bencode, bdecode

from copy import deepcopy
from sha import sha
from random import shuffle
import os

class Torrent:
    def __init__(self):
        self.announce = None
        self.amountOfTrackers = None
        self.creationDate = None
        self.comment = None
        self.createdBy = None
        self.torrentHash = None
        self.torrentName = None
        self.files = None
        self.pieceLength = None
        self.pieceHashes = None
        self.charset = None
        
    def _getFileIndexForOffset(self, offset):
        startPos = 0
        endPos = len(self.files)-1

        #search using divide and conquer
        while endPos - startPos > 5:        
            curPos = startPos + ((endPos - startPos)/2)
            startOffset = self.files[curPos]['offset']
            endOffset = startOffset + self.files[curPos]['size']
            
            if offset >= endOffset:
                #right
                startPos = curPos + 1
                    
            elif offset < startOffset:
                #left
                endPos = curPos - 1
            
            else:
                #match
                startPos = curPos
                endPos = curPos
                    
        place = endPos
        for i in xrange(startPos, endPos):
            startOffset = self.files[i]['offset']
            endOffset = startOffset + self.files[i]['size']
            if offset >= startOffset and offset < endOffset:
                #found the right spot
                place = i
                break
        
        return place

    def load(self, torrentdata):
        #decode torrentdata
        torrentdata = bdecode(torrentdata)
        
        #encoding
        if torrentdata.has_key('encoding'):
            self.charset = torrentdata['encoding']
        else:
            self.charset = 'UTF-8'
        
        #tracker urls
        self.announce = [[torrentdata['announce']]]
        self.amountOfTrackers = 1
        if torrentdata.has_key('announce-list'):
            self.amountOfTrackers = 0
            self.announce = torrentdata['announce-list']
            for tier in self.announce:
                shuffle(tier)
                self.amountOfTrackers += len(tier)
        
        #creation date of the torrent
        if torrentdata.has_key('creation date'):
            self.creationDate = torrentdata['creation date']
        else:
            self.creationDate = 0
        
        #torrent comment
        if torrentdata.has_key('comment'):
            self.comment = unicode(torrentdata['comment'], self.charset, 'ignore')
        else:
            self.comment = None
        
        #creator of the torrent
        if torrentdata.has_key('created by'):
            self.createdBy = unicode(torrentdata['created by'], self.charset, 'ignore')
        else:
            self.createdBy = None
        
        #torrent hash and name
        info = torrentdata['info']
        self.torrentHash = sha(bencode(info)).digest()
        self.torrentName = unicode(info['name'], self.charset, 'ignore')

        #files
        if info.has_key('files'):
            #multiple files
            self.files = []
            sizesum = 0
            for sfile in info['files']:
                #decode path
                for y in xrange(0, len(sfile['path'])):
                    sfile['path'][y] = unicode(sfile['path'][y], self.charset, 'ignore')
                #add to list
                size = sfile['length']
                self.files.append({'path':os.path.join(*sfile['path']),
                                   'size':size,
                                   'offset':sizesum})
                sizesum += size
            
            #add dir name
            dirName = unicode(info['name'], self.charset, 'ignore')
            for i in xrange(0, len(self.files)):
                filePath = os.path.normpath(os.path.join(dirName, self.files[i]['path']))
                if not filePath.startswith(dirName):
                    #dangerous relative stuff => ../ and the like
                    raise Exception('Security violation: file "%s" is not inside base directory "%s" (original path: "%s")' % (filePath, dirName, os.path.join((dirName, self.files[i]['path']))))
                else:
                    self.files[i]['path'] = filePath
            
        else:
            #only one file
            self.files = [{'path':os.path.normpath(unicode(info['name'], self.charset, 'ignore')),
                           'size':info['length'],
                           'offset':0}]            
        
        #piece length
        self.pieceLength = info['piece length']
        
        #piece hashes
        rawpieces = info['pieces']            
        self.pieceHashes = []
        place = 0
        while place<len(rawpieces):
            self.pieceHashes.append(rawpieces[place:place+20])
            place += 20

    ##torrent data
    def getCreator(self):
        return self.createdBy
    
    
    def getCreationDate(self):
        return self.creationDate
    

    def getComment(self):
        return self.comment
    
    
    def getName(self):
        return self.torrentName
    

    def getTorrentHash(self):
        return self.torrentHash
    

    def getTrackerList(self):
        return self.announce
    
    
    def getAmountOfTrackers(self):
        return self.amountOfTrackers

       
    
    
    ##files
    
    def getFiles(self):
        return deepcopy(self.files)
    

    def getAmountOfFiles(self):
        return len(self.files) 
    
    
    def getFilesForOffset(self, fromOffset, toOffset):
        assert toOffset <= self.getTotalSize(),'toOffset outside of valid range?!'
        
        #get last and first involved file
        firstFileIndex = self._getFileIndexForOffset(fromOffset)
        lastFileIndex = self._getFileIndexForOffset(toOffset-1)
        
        result = []
        #first result
        firstFile = self.files[firstFileIndex]
        firstFileResult = {'path':firstFile['path'],
                           'offset':fromOffset - firstFile['offset']}

        if firstFileIndex == lastFileIndex:
            #requested offset-range is inside of file
            firstFileResult['bytes'] = toOffset - firstFile['offset'] - firstFileResult['offset']
            result.append(firstFileResult)            
        else:
            #multiple files involvled
            firstFileResult['bytes'] = firstFile['size'] - firstFileResult['offset']
            result.append(firstFileResult)
            
            #intermediary results
            for place in xrange(firstFileIndex+1,lastFileIndex):
                fl = self.files[place]
                result.append({'path':fl['path'],
                              'offset':0,
                              'bytes':fl['size']})
            
            #last result
            fl = self.files[lastFileIndex]
            result.append({'path':fl['path'],
                           'offset':0,
                           'bytes':toOffset - fl['offset']})
        return result
    
    
    def getTotalSize(self):
        return self.files[-1]['offset'] + self.files[-1]['size']
    
    
    ##pieces
    
    def getPieceLength(self):
        return self.pieceLength
    
    def getTotalAmountOfPieces(self):
        return len(self.pieceHashes)
    
    
    def getPieceHashByOffset(self, offset):
        return self.pieceHashes[offset/self.pieceLength]
    

    def getPieceHashByPieceIndex(self, pieceIndex):
        return self.pieceHashes[pieceIndex]
    

    def convertPieceIndexToOffset(self, pieceIndex, addOffset = 0):
        return self.pieceLength * pieceIndex + addOffset


    def getLengthOfPiece(self, pieceIndex):
        if pieceIndex*self.pieceLength+self.pieceLength > self.getTotalSize():
            return self.getTotalSize() - pieceIndex*self.pieceLength
        else:
            return self.pieceLength
        

    def isValidPiece(self, pieceIndex):
        if pieceIndex>=0:
            toOffset = self.convertPieceIndexToOffset(pieceIndex)+\
                       self.getLengthOfPiece(pieceIndex)
            return toOffset<=self.getTotalSize()
        else:
            return False
    

    def isValidRequest(self, pieceIndex, offset, length):
        if pieceIndex>=0 and offset>=0 and length>0:
            toOffset = self.convertPieceIndexToOffset(pieceIndex)+\
                       offset + length
            return (toOffset <= self.getTotalSize() and offset+length <= self.pieceLength)
        else:
            return False
        
        
    def getStats(self):
        stats = {}
        stats['torrentName'] = self.torrentName
        stats['torrentSize'] = self.getTotalSize()
        stats['torrentCreator'] = self.createdBy
        stats['torrentCreationDate'] = self.creationDate
        stats['torrentComment'] = self.comment
        stats['torrentHash'] = self.torrentHash
        stats['trackerAmount'] = self.amountOfTrackers
        stats['fileAmount'] = len(self.files)
        stats['pieceAmount'] = len(self.pieceHashes)
        stats['pieceLength'] = self.pieceLength
        return stats
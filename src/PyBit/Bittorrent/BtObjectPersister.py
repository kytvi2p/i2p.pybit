"""
Copyright 2009  Blub

BtObjectPersister, a class for persisting per-torrent objects, using an instance of "ObjectPersister" internally.
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

from __future__ import with_statement
import logging

class BtObjectPersister:
    def __init__(self, persister, torrentIdent):
        self.persister = persister
        self.torrentIdent = torrentIdent
        self.log = logging.getLogger('BtPersister')
        
        
    def load(self, key):
        return self.persister.load(self.torrentIdent+'-'+key)
    
    
    def get(self, key, default=None):
        return self.persister.get(self.torrentIdent+'-'+key, default)
    
    
    def store(self, key, obj, encoding='base64', sync=False):
        self.persister.store(self.torrentIdent+'-'+key, obj, encoding, sync)
        
        
    def remove(self, key, strict=False, sync=False):
        self.persister.remove(self.torrentIdent+'-'+key, strict, sync)
        
        
    def removeAll(self):
        btKeys = self.persister.keys('^'+self.torrentIdent+'-')
        for key in btKeys:
            self.log.debug('Removing key "%s" from persister', key)
            self.persister.remove(key)
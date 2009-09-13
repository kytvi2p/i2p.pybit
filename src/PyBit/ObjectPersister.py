"""
Copyright 2009  Blub

ObjectPersister, a general class for storing and retrieving data in/from a sqlite database.
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

from Bittorrent.Bencoding import bencode, bdecode

from sqlite3 import dbapi2 as sqlite
import logging
import os
import threading

class debugLog:
    def debug(self, msg, *args):
        print msg % args
        
    def info(self, msg, *args):
        print msg % args

class ObjectPersister:
    def __init__(self, dbPath, log=None):
        self.dbPath = dbPath
        if type(log)==str:
            self.log = logging.getLogger(log)        
        else:
            self.log = log
        
        #load db
        if os.path.isfile(self.dbPath):
            #database exists
            self.db = sqlite.connect(self.dbPath)
        else:
            #database doesn't exist
            if self.log is not None:
                self.log.info("Database not found, creating one")
            self.db = sqlite.connect(self.dbPath)
            self._initDatabase(self.db)
            
        self.db.row_factory = sqlite.Row
        self.db.text_factory = str
        self.lock = threading.Lock()
    
    
    ##internal functions - db
        
    def _initDatabase(self, db):
        db.execute('CREATE TABLE dict ('\
                   'key TEXT PRIMARY KEY,'\
                   'value BINARY'\
                   ');')
        db.commit()
        
        
    def _load(self, key):
        self.lock.acquire()
        self.log.debug('Getting value for key "%s"', str(key))
        cursor = self.db.execute('SELECT value FROM dict WHERE key=?', (key,))
        result = cursor.fetchone()
        if result is not None:
            result = result['value']
        self.log.debug('Got value "%s"', str(result))
        self.lock.release()
        return result
        
        
    def _store(self, key, value):
        self.lock.acquire()
        self.log.debug('Storing key "%s" with value "%s"', str(key), str(value))
        cursor = self.db.execute('SELECT key FROM dict WHERE key=?', (key,))
        if cursor.fetchone() is None:
            #doesn't exist yet, insert
            self.db.execute('INSERT INTO dict VALUES (?, ?)', (key, value))
        else:
            #already exists, update
            self.db.execute('UPDATE dict SET value=? WHERE key=?', (value, key))
        self.db.commit()
        self.lock.release()
        
        
    def _close(self):
        self.lock.acquire()
        self.db.close()
        self.lock.release()
    
    
    ##external functions - db
    
    def load(self, key):
        dbResult = self._load(key)
        if dbResult is None:
            #unknown key
            raise Exception('Unknown key!')
        
        obj = bdecode(dbResult, extended=True)
        return obj
    
    
    def store(self, key, value):
        data = bencode(value, extended=True)
        self._store(key, data)
        
        
    def close(self):
        self._close()
        
    
    ##external functions - dict
    
    def get(self, key, default=None):
        try:
            result = self.load(key)
        except:
            result = default
        return result
"""
Copyright 2009  Blub

Logger, a class which simplifies logging within torrent classes by supporting fixed prefixes (usually the torrent ident)
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

import logging

class Logger:
    def __init__(self, logIdent, prefix, *args):
        self.log = logging.getLogger(logIdent)
        self.prefix = prefix % args
        
    
    def debug(self, msg, *args, **kwargs):
        self.log.debug(self.prefix + msg, *args, **kwargs)
        
        
    def info(self, msg, *args, **kwargs):
        self.log.info(self.prefix + msg, *args, **kwargs)
        
        
    def warning(self, msg, *args, **kwargs):
        self.log.warning(self.prefix + msg, *args, **kwargs)
        
        
    def warn(self, msg, *args, **kwargs):
        self.log.warn(self.prefix + msg, *args, **kwargs)
        
        
    def error(self, msg, *args, **kwargs):
        self.log.error(self.prefix + msg, *args, **kwargs)
        
        
    def critical(self, msg, *args, **kwargs):
        self.log.critical(self.prefix + msg, *args, **kwargs)
        
        
    def fatal(self, msg, *args, **kwargs):
        self.log.fatal(self.prefix + msg, *args, **kwargs)
        
        
    def log(self, level, msg, *args, **kwargs):
        self.log.log(level, self.prefix + msg, *args, **kwargs)
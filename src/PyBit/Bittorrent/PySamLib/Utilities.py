"""
Copyright 2009  Blub

Utilities, a collection of small functions and classes.
This file is part of PySamLib.

PySamLib is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published
by the Free Software Foundation, version 2.1 of the License.

PySamLib is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with PySamLib.  If not, see <http://www.gnu.org/licenses/>.
"""

from cStringIO import StringIO
from traceback import print_exc

def getTraceback():
    pseudoFile = StringIO()
    print_exc(file = pseudoFile)
    return pseudoFile.getvalue()
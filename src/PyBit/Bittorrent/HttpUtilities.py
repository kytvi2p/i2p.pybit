"""
Copyright 2009  Blub

HttpUtilities.py, a collection of functions to encode and decode complete http urls or parts of them.
Also includes a few regexes for http urls (both general urls and i2p urls).
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


import re
from urllib import quote, unquote, quote_plus, unquote_plus

#normal
httpUrlPrefixRegex = '^(?P<prefix>[^@/.:?=#]*)://'
httpUrlUserRegex = '(?P<user>[^@/.:?=#]*?)(?P<userFlag>@)?'
httpUrlAddrRegex = '(?P<address>[^@/:?=#]*)'
httpUrlPortRegex = '(?P<portFlag>:)?(?(portFlag)(?P<port>[0-9]*))'
httpUrlPathRegex = '(?P<path>(/[^@?=#]*)?)'
httpUrlParameterRegex = '(?P<parameterFlag>\?)?(?(parameterFlag)(?P<parameter>[^@/:?#]*))'
httpUrlAnchorRegex = '(?P<anchorFlag>#)?(?(anchorFlag)(?P<anchor>[^@/:?=]*))'
httpUrlEndRegex = '$'
httpUrlRegex = ''.join((httpUrlPrefixRegex, httpUrlUserRegex, httpUrlAddrRegex, httpUrlPortRegex, httpUrlPathRegex, httpUrlParameterRegex, httpUrlAnchorRegex, httpUrlEndRegex))
httpRelativeUrlRegex = ''.join((httpUrlPathRegex, httpUrlParameterRegex, httpUrlAnchorRegex, httpUrlEndRegex))
httpUrlRegexObj = re.compile(httpUrlRegex)
httpRelativeUrlRegexObj = re.compile(httpRelativeUrlRegex)

#i2p (subset of normal)
i2pDestHttpUrlAddrRegex = '(?P<address>[A-Za-z0-9\-~]{512,512}AAAA(.i2p){0,1})'
i2pDestHttpUrlAddrRegexObj = re.compile('^'+i2pDestHttpUrlAddrRegex+'$')
i2pDnsHttpUrlAddrRegex = '(?P<address>[^@/:?=#]*(.b32){0,1}.i2p)'
i2pHttpUrlAddrRegex = '(?P<address>([A-Za-z0-9\-~]{512,512}AAAA(.i2p){0,1})|([^@/:?=#]*(.b32){0,1}.i2p))'
i2pDestHttpUrlRegex = ''.join((httpUrlPrefixRegex, httpUrlUserRegex, i2pDestHttpUrlAddrRegex, httpUrlPortRegex, httpUrlPathRegex, httpUrlParameterRegex, httpUrlAnchorRegex, httpUrlEndRegex))
i2pDnsHttpUrlRegex = ''.join((httpUrlPrefixRegex, httpUrlUserRegex, i2pDnsHttpUrlAddrRegex, httpUrlPortRegex, httpUrlPathRegex, httpUrlParameterRegex, httpUrlAnchorRegex, httpUrlEndRegex))
i2pHttpUrlRegex = ''.join((httpUrlPrefixRegex, httpUrlUserRegex, i2pHttpUrlAddrRegex, httpUrlPortRegex, httpUrlPathRegex, httpUrlParameterRegex, httpUrlAnchorRegex, httpUrlEndRegex))
i2pDestHttpUrlRegexObj = re.compile(i2pDestHttpUrlRegex)
i2pDnsHttpUrlRegexObj = re.compile(i2pDnsHttpUrlRegex)
i2pHttpUrlRegexObj = re.compile(i2pHttpUrlRegex)


class HttpUtilitiesException(Exception):
    def __init__(self, reason, *args):
        self.reason = reason % args
        Exception.__init__(self, self.reason)


class HttpUrlParseException(HttpUtilitiesException):
    pass
    
    
##decode - url parameter

def splitUrlParameter(paras):
    if type(paras) == unicode:
        paras = paras.encode('UTF-8', 'ignore')
    paras = paras.split('&')
    decodedParas = {}
    for pair in paras:
        pair = pair.split('=')
        key = unicode(unquote(pair[0]), 'UTF-8', 'ignore')
        if len(pair) == 1:
            value = None
        else:
            value = unicode(unquote('='.join(pair[1:])), 'UTF-8', 'ignore')
        decodedParas[key] = value
    return decodedParas
    
    
def decodeUrlParameter(paras):
    if type(paras) == unicode:
        paras = paras.encode('UTF-8', 'ignore')
    paras = paras.split('&')
    decodedParas = []
    for pair in paras:
        pair = pair.split('=')
        key = unicode(unquote(pair[0]), 'UTF-8', 'ignore')
        if len(pair) == 1:
            decodedParas.append(key)
        else:
            value = unicode(unquote_plus('='.join(pair[1:])), 'UTF-8', 'ignore')
            decodedParas.append(key+u'='+value)
    return u'&'.join(decodedParas)
    
    
##decode - complete url

def splitUrl(url, allowRelative=False):
    #splits a encoded url into its decoded components
    if type(url) == unicode:
        url = url.encode('UTF-8', 'ignore')
    
    #split url
    urlItems = httpUrlRegexObj.match(url)
    if urlItems is None and allowRelative == False:
        #failed
        raise HttpUrlParseException('Url "%s" is invalid!', url)
    
    elif urlItems is None and allowRelative == True:
        #try relative url
        splittedUrl = splitRelativeUrl(url)
    
    else:
        #worked, decode url
        urlDict = urlItems.groupdict()
        splittedUrl = {}
        splittedUrl['prefix'] = unicode(unquote(urlDict['prefix']), 'UTF-8', 'ignore')
        if urlDict['userFlag'] is not None:
            splittedUrl['user'] = unicode(unquote(urlDict['user']), 'UTF-8', 'ignore')
        splittedUrl['address'] = unicode(unquote(urlDict['address']), 'UTF-8', 'ignore')
        if urlDict['portFlag'] is not None:
            splittedUrl['port'] = unicode(unquote(urlDict['port']), 'UTF-8', 'ignore')
        splittedUrl['path'] = unicode(unquote(urlDict['path']), 'UTF-8', 'ignore')
        if urlDict['anchorFlag'] is not None:
            splittedUrl['anchor'] = unicode(unquote(urlDict['anchor']), 'UTF-8', 'ignore')
        if urlDict['parameterFlag'] is not None:
            splittedUrl['parameter'] = splitUrlParameter(urlDict['parameter'])
    return splittedUrl
    

def splitRelativeUrl(url):
    #splits a encoded relative url into its decoded components
    if type(url) == unicode:
        url = url.encode('UTF-8', 'ignore')
    
    #split url
    urlItems = httpRelativeUrlRegexObj.match(url)
    if urlItems is None:
        raise HttpUrlParseException('Url "%s" is invalid!', url)
        
    #decode url
    urlDict = urlItems.groupdict()
    splittedUrl = {}
    splittedUrl['path'] = unicode(unquote(urlDict['path']), 'UTF-8', 'ignore')
    if urlDict['anchorFlag'] is not None:
        splittedUrl['anchor'] = unicode(unquote(urlDict['anchor']), 'UTF-8', 'ignore')
    if urlDict['parameterFlag'] is not None:
        splittedUrl['parameter'] = splitUrlParameter(urlDict['parameter'])
    return splittedUrl


def decodeUrl(url):
    #splits a encoded url into its decoded components
    if type(url) == unicode:
        url = url.encode('UTF-8', 'ignore')
    
    #split url
    urlItems = httpUrlRegexObj.match(url)
    if urlItems is None:
        raise HttpUrlParseException('Url "%s" is invalid!', url)
        
    #decode url
    urlDict = urlItems.groupdict()
    splittedUrl = []
    splittedUrl.append(unicode(unquote(urlDict['prefix']), 'UTF-8', 'ignore'))
    if urlDict['userFlag'] is not None:
        splittedUrl.append(unicode(unquote(urlDict['user']), 'UTF-8', 'ignore'))
        splittedUrl.append(u'@')
    splittedUrl.append(unicode(unquote(urlDict['address']), 'UTF-8', 'ignore'))
    if urlDict['portFlag'] is not None:
        splittedUrl.append(u':')
        splittedUrl.append(unicode(unquote(urlDict['port']), 'UTF-8', 'ignore'))
    splittedUrl.append(unicode(unquote(urlDict['path']), 'UTF-8', 'ignore'))
    if urlDict['anchorFlag'] is not None:
        splittedUrl.append(u'#')
        splittedUrl.append(unicode(unquote(urlDict['anchor']), 'UTF-8', 'ignore'))
    if urlDict['parameterFlag'] is not None:
        splittedUrl.append(u'?')
        splittedUrl.append(decodeUrlParameter(urlDict['parameter']))
    return  u''.join(splittedUrl)
    
    
##encode - url parameter

def joinUrlParameter(paras):
    encodedParas = []
    for key, value in paras.iteritems():
        if type(key) == unicode:
            key = key.encode('UTF-8', 'ignore')
        if type(value) == unicode:
            value = value.encode('UTF-8', 'ignore')
        encodedParas.append(quote_plus(key))
        if value is not None:
            encodedParas.append('=')
            encodedParas.append(quote_plus(value))
        encodedParas.append('&')
    if len(encodedParas) > 0:
        del encodedParas[-1]
    return ''.join(encodedParas)


def joinRelativeUrl(url):
    return joinUrlParts(path=url.get('path', None), anchor=url.get('anchor', None), parameter=url.get('parameter', None))


def joinUrl(url):
    return joinUrlParts(url.get('address', None), url.get('prefix', None), url.get('user', None), url.get('port', None),
                        url.get('path', None), url.get('anchor', None), url.get('parameter', None))
    
    
def joinUrlParts(address=None, prefix='http://', user=None, port=None, path=None,  anchor=None, parameter=None):
    #encode unicode
    if isinstance(address, unicode):
        address = address.encode('UTF-8', 'ignore')
    if isinstance(prefix, unicode):
        prefix = prefix.encode('UTF-8', 'ignore')
    if isinstance(user, unicode):
        user = user.encode('UTF-8', 'ignore')
    if isinstance(port, unicode):
        port = port.encode('UTF-8', 'ignore')
    if isinstance(path, unicode):
        path = path.encode('UTF-8', 'ignore')
    if isinstance(anchor, unicode):
        anchor = anchor.encode('UTF-8', 'ignore')
        
    #check for weirdness
    if address is not None and address == '':
        address = None
    if prefix is not None and prefix == '':
        prefix = None
    if user is not None and user == '':
        user = None
    if port is not None and port == '':
        port = None
    if path is not None and path == '':
        path = None
    if anchor is not None and anchor == '':
        anchor = None
        
    #encode url
    url = []
    if address is not None:
        if prefix is not None:
            url.append(quote(prefix))
            url.append('://')
        if user is not None:
            url.append(quote(user))
            url.append('@')
        url.append(quote(address))
        if port is not None:
            url.append(':')
            url.append(quote(port))
    if path is not None:
        url.append(quote(path))
    elif (anchor is not None) or (parameter is not None) or (address is None):
        url.append('/')
    if parameter is not None:
        url.append('?')
        url.append(joinUrlParameter(parameter))
    if anchor is not None:
        url.append('#')
        url.append(quote(anchor))
    return ''.join(url)
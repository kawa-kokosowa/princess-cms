#!/usr/local/bin/python
import Cookie
import os

# fetch cookie
if 'HTTP_COOKIE' in os.environ and os.environ.get('HTTP_COOKIE') != '':
    cookie_string = os.environ.get('HTTP_COOKIE')
    cookie = Cookie.SimpleCookie()
    cookie.load(cookie_string)
    print "Content-type: text/html\n\n"
    print cookie['test'].value

    for key, value in cookie.iteritems():
      print '<strong>'
      print key
      print ': </strong>'
      print value
      print '<br>'

    print 'derp'

# set cookie
else:
    cookie = Cookie.SimpleCookie()
    cookie['test'] = 'success'
    print cookie

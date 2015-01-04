#!/usr/local/bin/python
"""Parses files in the content directory."""


import os
import sys
import SocketServer
import BaseHTTPServer
import CGIHTTPServer


LISTEN_ADDRESS = '127.0.0.1'
LISTEN_PORT = 8080
PUBLIC_DIRECTORY = 'www'


class ThreadingCGIServer(SocketServer.ThreadingMixIn,
                   BaseHTTPServer.HTTPServer):

    pass


def httpd():
    """THIS IS A TOY. It is only here so users may test parsed
    contents before making them public.

    """

    handler = CGIHTTPServer.CGIHTTPRequestHandler
    handler.cgi_directories = ['/']
    server = ThreadingCGIServer((LISTEN_ADDRESS, LISTEN_PORT), handler)
    os.chdir(PUBLIC_DIRECTORY)

    try:

        while 1:
            sys.stdout.flush()
            server.handle_request()

    except KeyboardInterrupt:
        print "Finished"


httpd()


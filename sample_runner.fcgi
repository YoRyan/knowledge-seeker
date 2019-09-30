#!/usr/bin/python3
from flup.server.fcgi import WSGIServer
from knowledgeseeker import create_app

if __name__ == '__main__':
    WSGIServer(create_app(), bindAddress='/run/knowledge-seeker.sock').run()

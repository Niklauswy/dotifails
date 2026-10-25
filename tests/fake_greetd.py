#!/usr/bin/env python3
"""A tiny greetd stand-in for greeter tests: speaks greetd's IPC (u32 length + JSON) on a Unix socket.

Usage: fake_greetd.py SOCKET PASSWORD LOG [DELAY]
DELAY (seconds) holds the verdict like pam_faildelay. It accepts PASSWORD for any user, records every request (passwords redacted) as JSON lines in LOG and
exits after a successful start_session. It never starts anything.
"""
import json
import os
import socket
import struct
import sys
import time

path, password, log = sys.argv[1:4]
delay = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
if os.path.exists(path):
    os.unlink(path)
server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(path)
server.listen(4)


def receive(connection, size):
    data = b''
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise ConnectionError
        data += chunk
    return data


def send(connection, payload):
    body = json.dumps(payload).encode()
    connection.sendall(struct.pack('=I', len(body)) + body)


def record(entry):
    with open(log, 'a') as stream:
        stream.write(json.dumps(entry) + '\n')


done = False
while not done:
    connection, _ = server.accept()
    try:
        while True:
            size = struct.unpack('=I', receive(connection, 4))[0]
            request = json.loads(receive(connection, size))
            kind = request.get('type')
            if kind == 'post_auth_message_response':
                accepted = request.get('response') == password
                time.sleep(delay)
                record({'type': kind, 'accepted': accepted})
                send(connection, {'type': 'success'} if accepted else
                     {'type': 'error', 'error_type': 'auth_error', 'description': 'Authentication failure'})
            else:
                record(request)
                if kind == 'create_session':
                    send(connection, {'type': 'auth_message', 'auth_message_type': 'secret', 'auth_message': 'Password: '})
                else:
                    send(connection, {'type': 'success'})
                if kind == 'start_session':
                    done = True
                    break
    except (ConnectionError, struct.error):
        pass
    finally:
        connection.close()
server.close()
os.unlink(path)

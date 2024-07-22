
'''
client.py - basic TCP/UDP client listener

Usage:
    client.py tcp --address=IP [--port=PORT]
    client.py udp [--port=PORT]

Options:
    --address=IP           TCP address: [default: localhost]
    --port=PORT            Port [default: 55554]

'''

import socket
from docopt import docopt

config = docopt(__doc__)

if config['tcp']:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print('TCP connection to {} on port {}'.format(config['--address'], config['--port']))
    s.connect((config['--address'], int(config['--port'])))
else:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    print('UDP connection on port {}'.format(config['--port']))
    s.bind(('0.0.0.0', int(config['--port'])))

while True:
    buf = s.recv(1024)
    if len(buf) == 0:
        print('Connection closed - bye')
        break

    print(buf.decode('utf8'), end='')

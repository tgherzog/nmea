
'''
client.py - basic TCP client listener

Usage:
    client.py [--address=addr] [--port=port]

Options:
    --address=addr         TCP address: [default: localhost]
    --port=port            Port [default: 5001]

'''

import socket
from docopt import docopt

config = docopt(__doc__)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

print('Connecting to {} on port {}'.format(config['--address'], config['--port']))
s.connect((config['--address'], int(config['--port'])))

while True:
    buf = s.recv(1024)
    if len(buf) == 0:
        print('Connection closed - bye')
        break

    print(buf.decode('utf8'), end='')

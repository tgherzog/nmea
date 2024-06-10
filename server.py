
import socket
from time import sleep

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('localhost', 5001))
s.listen(5) # maximum number of connections. Omit to allow it to choose a reasonable default
print('Server open: port 5001')

while True:
    try:
        print('Waiting to accept. Type Ctrl-C to quit server')
        conn,addr = s.accept()
    except:
        break

    print('Client open: {}:{}'.format(addr[0], addr[1]))
    try:
        n = 0
        while True:
            n += 1
            conn.send('Sending: {}\r\n'.format(n).encode('utf8'))
            sleep(4)
    except KeyboardInterrupt:
        print('\nClosing connection.')
        conn.shutdown(socket.SHUT_RDWR)
        conn.close()
    except Exception as err:
        print('Error - closing ({})'.format(err))
        pass

print('Closing server - bye')
# s.shutdown(socket.SHUT_RDWR)
s.close()

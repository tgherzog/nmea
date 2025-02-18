
'''
Usage:
    emulator.py tcp [--port=PORT] [--data=FILE] [--types=TYPES] [--timer=DELAY]
    emulator.py udp [--port=PORT] [--address=IP] [--data=FILE] [--types=TYPES] [--timer=DELAY]

Options:
    --data=FILE        source data from file; overrides --types
    --port=PORT        port number [default: 55554]
    --address=IP       broadcast address [default: 255.255.255.255]
    --types=TYPES      sentences to send: see list [default: WIMWD,PSTW,SDDBK]
    -t --timer=DELAY   seconds delay between sentence clusters [default: 1.0]

Supported sentences:
    WIMWD
    WIMWV
    PSTW
    SDDBT
    SDDBK
    SDDBS

'''

from docopt import docopt
import socket
import select
import time
import random
import sys
import math as m

config = docopt(__doc__)
port = int(config['--port'])
types = config['--types'].split(',')

def ang_norm(a):
    if a < 0:
        a += 360

    while a >= 360:
        a -= 360

    return a

def checksum(s):
    '''compute checksum of an NMEA sentence, skipping the prefixing '$'
       and returning the result formatted as "*XX"
    '''

    cs = 0
    for i in s[1:]:
        cs ^= ord(i)

    return '*{:02X}'.format(cs)

# All AWS and AWA calculations are derived from the law of cosines, where wind and vessel speeds
# are the sides of a triangle, and wind angles, directions are courses are the angles of the triangle.
# for apparent wind, the value is actually the "outside" of the angle, so 180-b

# Therefore, all calculations below are derived from these two formulas:
# law of cosines:
#   C^2 = A^2 + B^2 - 2ABcos(c)
#   cos(c) = (A^2 + B^2 - C^2) / 2AB
# and:
#   cos(180-b) = cos(b') = -cos(b)

def true_from_apparent(awa, aws, sog):

    awa  = ang_norm(awa)
    _awa = m.radians(awa)
    tws  = aws**2 + sog**2 - 2*aws*sog*m.cos(_awa)
    tws  = m.sqrt(tws)

    _twa = (aws**2 - sog**2 - tws**2) / (2*sog*tws)
    _twa = m.acos(_twa)
    twa  = m.degrees(_twa)

    # correct for port
    if awa > 180:
        twa = 360 - twa

    return (twa,tws)

def apparent_from_true(twa, tws, sog):

    twa = ang_norm(twa)
    _twa = m.radians(twa)
    aws  = sog**2 + tws**2 + 2*sog*tws*m.cos(_twa)
    aws  = m.sqrt(aws)

    _awa = (sog**2 + aws**2 - tws**2) / (2*sog*aws)
    _awa = m.acos(_awa)
    awa  = m.degrees(_awa)

    # correct for port
    if twa > 180:
        awa = 360 - awa

    return(awa,aws)

if __name__ == '__main__':
    initWindDir = 60
    windDirVar = 15
    initWindSpeed = 15
    windSpeedVar = 3
    sog = 3.5
    cog = 45
    initDBT = 12*12
    depthVar = 5*12
    draft = 47 # inches
    dbsOffset = 20 # inches

    random.seed()
    conn = None
    sending = True

    if config['--data']:
        fd = open(config['--data'], 'r')
        fd.seek(0, 2)  # end of file
        fd_len = fd.tell()
        fd.seek(0, 0)

    if config['tcp']:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(('192.168.255.255',1))
        ip = s.getsockname()[0]
        s.close()

        clients = [None] * 10
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((ip, port))
        s.listen(len(clients))
        print('> Listening for TCP connections on {}:{}'.format(ip, port))
        print('> Type Ctrl-C to quit')

    elif config['udp']:
        clients = []
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setblocking(False)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print('> Broadcasting via UDP on {}:{}'.format(config['--address'], port))
    else:
        sys.exit('Config error')


    def send(nmea):
        global sending, clients

        if not sending:
            return

        nmea += checksum(nmea)
        print(nmea)
        if config['tcp'] and conn:
            for i in range(len(clients)):
                if clients[i] is not None:
                    try:
                        clients[i].send(bytes((nmea+'\r\n').encode('utf-8')))
                    except KeyboardInterrupt:
                        sending = False
                        return
                    except Exception as err:
                        clients[i] = None
                        print('> Connection closed ({})'.format(err))
                        print('> {} open connections'.format(len(clients) - clients.count(None)))

        elif config['udp']:
            s.sendto(bytes((nmea+'\r\n').encode('utf-8')), (config['--address'], port))
        
    while sending:
        if config['tcp']:
            # check for new clients
            readable,writable,errored = select.select([s] + [i for i in clients if i is not None], [], [], 0)
            for elem in readable:
                if elem is s:
                    conn,addr = s.accept()
                    for i in range(len(clients)):
                        if clients[i] is None:
                            clients[i] = conn
                            break

                    print('> New Connection from {}'.format(addr))
                    print('> {} open connections'.format(len(clients) - clients.count(None)))

            if len(clients) - clients.count(None) == 0:
                continue


        if config['--data']:
            if fd.tell() == fd_len:
                break

            send(fd.readline().split('*')[0])
        else:
            # generate all values at once to avoid confusion
            apparentWindAngle = ang_norm(initWindDir + random.randint(-windDirVar, windDirVar))
            apparentWindSpeed  = initWindSpeed + random.randint(-windSpeedVar*10, windSpeedVar*10) / 10
            (trueWindAngle,trueWindSpeed) = true_from_apparent(apparentWindAngle,apparentWindSpeed, sog)
            apparentWindAngleToNorth = apparentWindAngle + cog
            trueWindAngleToNorth = trueWindAngle + cog

            depth = initDBT + random.randint(-depthVar, depthVar)

            # MWD: true wind speed & direction (relative to compass north)
            if 'WIMWD' in types:
                ang = int(round(trueWindAngleToNorth,0))
                spd = trueWindSpeed
                send('$WIMWD,{},T,{},M,{:.1f},N,{:.1f},M'.format(ang, ang+11, spd, spd*0.51444))

            # PSTW: apparent wind speed & direction (relative to compass north)
            if 'PSTW' in types:
                ang = int(round(apparentWindAngleToNorth,0))
                spd = apparentWindSpeed
                send('$PSTW,{},T,{},M,{:.1f},N,{:.1f},M'.format(ang, ang+11, spd, spd*0.51444))

            # WMV: apparent wind speed & direction (relative to heading)
            if 'WIMWV' in types:
                ang = int(round(apparentWindAngle,0))
                spd = apparentWindSpeed
                send('$WIMWV,{},R,{:.1f},N,A'.format(ang, spd))


            if 'SDDBT' in types:
                d = depth
                send('$SDDBT,{:.1f},f,{:.1f},M,{:.1f},F'.format(d/12, d*.0254, d/72))

            if 'SDDBK' in types:
                d = depth+dbsOffset-draft
                send('$SDDBK,{:.1f},f,{:.1f},M,{:.1f},F'.format(d/12, d*.0254, d/72))

            if 'SDDBS' in types:
                d = depth+dbsOffset
                send('$SDDBS,{:.1f},f,{:.1f},M,{:.1f},F'.format(d/12, d*.0254, d/72))

        try:
            time.sleep(float(config['--timer']))
        except:
            sending = False

    for conn in clients:
        if conn is not None:
            conn.shutdown(socket.SHUT_RDWR)
            conn.close()
        
    s.close()


'''
Usage:
    emulator.py tcp [--port=PORT] [--types=TYPES]
    emulator.py udp [--port=PORT] [--types=TYPES]

Options:
    --port=PORT        port number [default: 55554]
    --types=TYPES      sentences to send: see list [default: WIMWD,PSTW,SDDBK]

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

    if config['tcp']:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(('192.168.255.255',1))
        ip = s.getsockname()[0]
        s.close()

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((ip, port))
        s.listen(1)
        print('Listening for TCP connections on {}:{}'.format(ip, port))
        print('Type Ctrl-C to quit')
        try:
            conn,addr = s.accept()
            print('Connection open: {}:{}'.format(addr[0], addr[1]))
        except:
            s.close()
            sys.exit(0)

    elif config['udp']:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setblocking(False)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print('Broadcasting via UDP on port {}'.format(port))
        conn = None
    else:
        sys.exit('Config error')


    def send(nmea):
        global conn, sending

        nmea += checksum(nmea)
        if config['tcp'] and conn:
            try:
                print(nmea)
                conn.send(bytes((nmea+'\r\n').encode('utf-8')))
            except KeyboardInterrupt:
                conn.shutdown(socket.SHUT_RDWR)
                conn.close()
                conn = None
                sending = False
            except Exception as err:
                print('Error ({})'.format(err))
                conn = None
                sending = False

        elif config['udp']:
            print(nmea)
            s.sendto(bytes((nmea+'\r\n').encode('utf-8')), ('255.255.255.255', port))
        
    while sending:
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
            time.sleep(1.0)
        except:
            sending = False

    if conn:
        conn.shutdown(socket.SHUT_RDWR)
        conn.close()
        
    s.close()

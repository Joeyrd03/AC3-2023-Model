#code for sockets in python This just "dials the phone"
#import socket
#mysock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#mysock.connect(('data.pr4e.org', 80))

# we need to use this to bring data into python
# to make an http request, it must start with GET

#HTTP request for python

import socket

mysock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
mysock.connect(('data.pr4e.org', 80))
cmd = 'GET http://data.pr4e.org/romeo.txt HTTP/1.0\r\n\r\n'.encode()
mysock.send(cmd)

while True:
    data = mysock.recv(512)
    if (len(data) <1):
        break
    print(data.decode())
mysock.close()
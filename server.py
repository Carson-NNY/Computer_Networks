#
# Columbia University - CSEE 4119 Computer Networks
# Assignment 1 - Adaptive video streaming
#
# server.py - the server program for taking request from the client and
#             send the requested file back to the client
#

import socket
import sys
import os
import struct

if len(sys.argv) != 2:
    print("Usage: python server.py <port>")
    sys.exit(1)

serverPort = int(sys.argv[1])

serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
serverSocket.bind(('', serverPort))
serverSocket.listen(1)
print(f"The server is ready to receive on port {serverPort}")

while True:
    connectionSocket, addr = serverSocket.accept()
    print(f"Connected by: {addr}")

    while True:
        try:
            sentence = connectionSocket.recv(1024).decode().strip()
            if not sentence:
                break

            tokens = sentence.split()

            if tokens[0] == "manifest.mpd":
                if len(tokens) < 2:
                    continue

                video_name = tokens[1]
                manifest_path = os.path.join("data", video_name, tokens[0])

                if not os.path.exists(manifest_path):
                    connectionSocket.sendall(b'0')
                    continue

                with open(manifest_path, "rb") as file:
                    data = file.read()

                connectionSocket.sendall(b'1')
                manifest_len = len(data)
                connectionSocket.sendall(struct.pack("!I", manifest_len))
                connectionSocket.sendall(data)

            elif len(tokens) == 3:  # Chunk request
                video_name, bitrate, chunk_no = tokens
                chunk_filename = f"{video_name}_{bitrate}_{int(chunk_no):05d}.m4s"
                chunk_path = os.path.join("data", video_name, "chunks", chunk_filename)


                if not os.path.exists(chunk_path):
                    connectionSocket.sendall(b'0')
                    continue

                with open(chunk_path, "rb") as file:
                    data = file.read()

                connectionSocket.sendall(b'1')
                chunk_len = len(data)
                connectionSocket.sendall(struct.pack("!I", chunk_len))

                connectionSocket.sendall(data)

        except ConnectionResetError:
            print("Client disconnected.")
            break

    connectionSocket.close()
    print("Connection closed.")


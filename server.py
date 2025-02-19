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

    while True:  # Keep connection open for multiple requests
        try:
            sentence = connectionSocket.recv(1024).decode().strip()
            if not sentence:
                break  # Exit loop if client disconnects

            print(f"Client requested: {sentence}")
            tokens = sentence.split()

            if len(tokens) == 1:  # Manifest request
                video_name = tokens[0]
                manifest_path = os.path.join("data", video_name, "manifest.mpd")

                if not os.path.exists(manifest_path):
                    connectionSocket.sendall("video not found".encode())
                    continue
                with open(manifest_path, "rb") as file:
                    print(f"Sending manifest file: {file}")
                    data = file.read()

                manifest_len = len(data)
                connectionSocket.sendall(struct.pack("!I", manifest_len))
                connectionSocket.sendall(data)
                print("Manifest sent.")

            elif len(tokens) == 3:  # Chunk request
                print("Chunk request entered")
                video_name, bitrate, chunk_no = tokens
                chunk_filename = f"{video_name}_{bitrate}_{int(chunk_no):05d}.m4s"
                chunk_path = os.path.join("data", video_name, "chunks", chunk_filename)

                print(f"Requested chunk: {chunk_path}")

                if not os.path.exists(chunk_path):
                    connectionSocket.sendall("video not found".encode())
                    continue

                with open(chunk_path, "rb") as file:
                    data = file.read()

                chunk_len = len(data)
                # send the length of the chunk first
                connectionSocket.sendall(struct.pack("!I", chunk_len))

                # print(f"Sending chunk file: {file}")
                connectionSocket.sendall(data)

        except ConnectionResetError:
            print("Client disconnected.")
            break

    connectionSocket.close()
    print("Connection closed.")


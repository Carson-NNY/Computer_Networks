#
# Columbia University - CSEE 4119 Computer Networks
# Assignment 1 - Adaptive video streaming
#
# client.py - the client program for sending request to the server and play the received video chunks
#
# from video_player import play_chunks
import threading
from queue import Queue
import sys
import socket
import os
import xml.etree.ElementTree as parser


def client(server_addr, server_port, video_name, alpha, chunks_queue):
    """
    the client function
    write your code here

    arguments:
    server_addr -- the address of the server
    server_port -- the port number of the server
    video_name -- the name of the video
    alpha -- the alpha value for exponentially-weighted moving average
    chunks_queue -- the queue for passing the path of the chunks to the video player
    """

    # create a socket and connect to the server
    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    clientSocket.connect((server_addr, server_port))

    # send the video name to request the manifest file
    clientSocket.send(video_name.encode())

    print("test11111")
    # receive the manifest file response
    response = b""
    while True:
        data = clientSocket.recv(4096)
        if not data or b"manifest_end" in data:
            response += data.replace(b"manifest_end", b"")
            break
        response += data

    response_str = response.decode(errors="replace").strip()
    # clientSocket.close()

    # Check if the received response is empty
    if not response_str:
        print("No data received from server.")
        return

    # Check if the video was not found
    if "video not found" in response_str:
        print("video not found")
        return

    print(f"Received manifest before parsing:\n{response_str}")

    # parse the manifest XML to determine the lowest bitrate
    try:
        root = parser.fromstring(response_str)
        representation_elements = root.findall(".//Representation")
        if not representation_elements:
            print("No representations found in manifest.")
            return

        bitrates = []
        for rep in representation_elements:
            bw = rep.get("bandwidth")
            if bw is not None:
                bitrates.append(int(bw))

        if not bitrates:
            print("No valid bitrates in manifest.")
            return

        lowest_bitrate = min(bitrates)
        print(f"Lowest bitrate: {lowest_bitrate}")
    except parser.ParseError:
        print("Error parsing manifest XML.")
        return


    # create a new connection to request the first chunk at the lowest bitrate
    # clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # clientSocket.connect((server_addr, server_port))

    # construct the request for the first chunk (chunk 0)
    chunk_request = f"{video_name} {lowest_bitrate} 0"

    print(f"Requesting first chunk: {chunk_request}")
    clientSocket.sendall(chunk_request.encode())
    print("successfully sent request")

    # receive the chunk data
    chunk_data = b""
    while True:
        data = clientSocket.recv(4096)
        if not data:
            break
        chunk_data += data

    clientSocket.close()

    # check if the chunk was not found
    if b"video not found" in chunk_data:
        print("video not found for chunk")
        return

    # create temporary directory if not exist
    if not os.path.exists("tmp"):
        os.makedirs("tmp")

    # write chunk to the temporary directory
    chunk_filepath = os.path.join("tmp", "chunk_0.m4s")
    with open(chunk_filepath, "wb") as f:
        f.write(chunk_data)

    print(f"Saved first chunk at {chunk_filepath}")

    # put the path of the chunk to the queue
    chunks_queue.put(chunk_filepath)


# parse input arguments and pass to the client function
if __name__ == '__main__':
    server_addr = sys.argv[1]
    server_port = int(sys.argv[2])
    video_name = sys.argv[3]
    alpha = float(sys.argv[4])

    # init queue for passing the path of the chunks to the video player
    chunks_queue = Queue()
    # start the client thread with the input arguments
    client_thread = threading.Thread(target=client, args=(server_addr, server_port, video_name, alpha, chunks_queue))
    client_thread.start()
    # start the video player
    # play_chunks(chunks_queue)

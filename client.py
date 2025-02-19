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
import struct

def receive_data(clientSocket):
    """
    Receives the manifest file from the server and returns it as a decoded string.
    """
    manifest_len_bi = clientSocket.recv(4)
    if not manifest_len_bi:
        print("Failed to receive manifest_len_bi")
        exit()
    manifest_len = struct.unpack("!I", manifest_len_bi)[0]
    print(f"=====Expected manifest file length: {manifest_len} bytes=======")

    res = b""
    while len(res) < manifest_len:
        data = clientSocket.recv(min(4096, manifest_len - len(res)))  # 4096?????????????  Adjust read size dynamically
        if not data in data:
            break
        res += data

    # return manifest_data.decode(errors="replace").strip()
    return res

def parse_manifest(mani_file):
    """
    Parses the manifest XML and returns:
    - Number of chunks
    - Lowest bitrate available
    """
    try:
        root = parser.fromstring(mani_file)
        media_presentation_duration = float(root.attrib.get("mediaPresentationDuration", 0))
        max_segment_duration = float(root.attrib.get("maxSegmentDuration", 1))

        # Compute the number of chunks
        num_chunks = int(media_presentation_duration / max_segment_duration)


        # Extract available bitrates
        representation_elements = root.findall(".//Representation")
        if not representation_elements:
            print("No representations found in manifest.")
            return None, None

        bitrates = [int(rep.get("bandwidth")) for rep in representation_elements if rep.get("bandwidth") is not None]

        if not bitrates:
            print("No valid bitrates in manifest.")
            return None, None

        lowest_bitrate = min(bitrates)

        return num_chunks, lowest_bitrate

    except parser.ParseError:
        print("Error parsing manifest XML.")
        return None, None


def check_video_not_found(data):
    """
    Checks if the response data contains "video not found".
    Returns True if the video is not found, otherwise False.
    """
    if b"video not found" in data:
        print("video not found")
        return True
    return False


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

    mani_file = receive_data(clientSocket).decode(errors="replace").strip()

    # Check if the received response is empty
    if not mani_file:
        print("No data received from server.")
        return
    # Check if the video was not found
    if check_video_not_found(mani_file.encode()):
        clientSocket.close()
        return

    print(f"---Received manifest before parsing:\n{mani_file}")

    # parse the manifest file
    num_chunks, lowest_bitrate = parse_manifest(mani_file)
    if num_chunks is None or lowest_bitrate is None:
        print("Failed to parse manifest.")
        return

    print(f"Number of chunks: {num_chunks}")
    print(f"Lowest bitrate: {lowest_bitrate}")

    chunk_request = f"{video_name} {lowest_bitrate} 0"

    clientSocket.sendall(chunk_request.encode())
    print("successfully sent chunk request: ", chunk_request)

    first_chunk = receive_data(clientSocket)
    if check_video_not_found(first_chunk):
        clientSocket.close()
        return

    # create temporary directory if not exist
    if not os.path.exists("tmp"):
        os.makedirs("tmp")

    # write chunk to the temporary directory
    chunk_filepath = os.path.join("tmp", "chunk_0.m4s")
    with open(chunk_filepath, "wb") as f:
        f.write(first_chunk)

    print("successfully received chunk: ", first_chunk)
    print(f"Saved first chunk at {chunk_filepath}")

    for i in range(1, num_chunks):
        # calculate the next bitrate
        chunk_request = f"{video_name} {lowest_bitrate} {i}"
        clientSocket.sendall(chunk_request.encode())
        print(f"successfully requested chunk: {chunk_request}")

        # receive the chunk data
        rest_chunk = receive_data(clientSocket)
            # data = clientSocket.recv(4096)
            # if not data or b"end_chunk" in data:
            #     chunk_data += data.replace(b"end_chunk", b"")
            #     break
            # chunk_data += data

        # check if the chunk was not found
        if check_video_not_found(rest_chunk):
            clientSocket.close()
            return

        # write chunk to the temporary directory
        chunk_filepath = os.path.join("tmp", f"chunk_{i}.m4s")
        with open(chunk_filepath, "wb") as f:
            f.write(rest_chunk)

        print(f"Saved chunk {i} at {chunk_filepath}")

    clientSocket.close()
    # put the path of the chunk to the queue
    # chunks_queue.put(chunk_filepath)


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

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
import time

def request_rest_chunk(client_socket, video_name, first_throughput, num_chunks, sorted_bitrates, alpha):
    """
    Requests and receives the rest of the chunks from the server.
    """

    avg_throughput = first_throughput

    for i in range(1, num_chunks):
        # calculate the next bitrate
        bitrate = sorted_bitrates[0]
        for bit in reversed(sorted_bitrates):
            # print(f"bit: {bit}, avg_throughput: {avg_throughput}")
            if avg_throughput >= 1.5 * bit:
                bitrate = bit
                break
        # print( f"Chunk {i}: Bitrate {bitrate} bps | EWMA Throughput {avg_throughput:.2f} bps")

        chunk_request = f"{video_name} {bitrate} {i}"
        print(f"Requesting chunk {i} with bitrate {bitrate} bps")
        t_s = time.time()
        client_socket.sendall(chunk_request.encode())
        # receive the chunk data
        rest_chunk, data_size_bit = receive_data(client_socket)
        # print(f"data_size_bit: {data_size_bit} bits")
        t_f = time.time()
        duration = t_f - t_s

        # Calculate throughput
        if duration > 0:
            current_throughput = data_size_bit / duration
            avg_throughput = alpha * current_throughput + (1 - alpha) * avg_throughput
        else:
            current_throughput = 0
        # print(f"current_throughput: {current_throughput} bits/sec")

        # check if the chunk was not found
        if check_video_not_found(rest_chunk):
            client_socket.close()
            return

        # write chunk to the temporary directory
        chunk_filepath = os.path.join("tmp", f"chunk_{i}.m4s")
        with open(chunk_filepath, "wb") as f:
            f.write(rest_chunk)
        print(f"Saved chunk {i} at {chunk_filepath}")
        # put the path of the chunk to the queue
        # chunks_queue.put(chunk_filepath)

def receive_data(clientSocket):
    """
    Receives the manifest/video file from the server and returns it as a decoded string.
    """

    file_size = clientSocket.recv(4)
    if not file_size:
        print("Failed to receive file")
        exit()
    data_size_byte = struct.unpack("!I", file_size)[0]
    data_size_bit = data_size_byte * 8
    print(f"=====Expected file length: {data_size_byte} bytes=======")

    res = b""
    while len(res) < data_size_byte:
        data = clientSocket.recv(min(4096, data_size_byte - len(res)))  # 4096?????????????  Adjust read size dynamically
        if not data:
            break
        res += data


    return res, data_size_bit

def parse_manifest(mani_file):
    """
    Parses the manifest XML and returns:
    - Number of chunks
    - Lowest bitrate available
    - Sorted list of available bitrates (ascending order)
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
            return None, None, None

        bitrates = [int(rep.get("bandwidth")) for rep in representation_elements if rep.get("bandwidth") is not None]

        if not bitrates:
            print("No valid bitrates in manifest.")
            return None, None, None

        sorted_bitrates = sorted(bitrates)
        lowest_bitrate = sorted_bitrates[0]

        return num_chunks, lowest_bitrate, sorted_bitrates

    except parser.ParseError:
        print("Error parsing manifest XML.")
        return None, None, None



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
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_addr, server_port))

    # send the video name to request the manifest file
    client_socket.send(video_name.encode())

    mani_file, mani_size_bit = (receive_data(client_socket))
    mani_file = mani_file.decode(errors="replace").strip()

    # Check if the received response is empty
    if not mani_file:
        print("No data received from server.")
        return
    # Check if the video was not found
    if check_video_not_found(mani_file.encode()):
        client_socket.close()
        return

    print(f"---Received manifest before parsing:\n{mani_file}")

    # parse the manifest file
    num_chunks, lowest_bitrate, sorted_bitrates = parse_manifest(mani_file)
    if num_chunks is None or lowest_bitrate is None:
        print("Failed to parse manifest.")
        return

    print(f"Number of chunks: {num_chunks}")
    print(f"Lowest bitrate: {lowest_bitrate}")

    chunk_request = f"{video_name} {lowest_bitrate} 0"

    t_s = time.time()
    client_socket.sendall(chunk_request.encode())
    print("successfully sent chunk request: ", chunk_request)
    # receive the first chunk data
    first_chunk, first_chunk_size_bit = receive_data(client_socket)
    t_f = time.time()
    duration = t_f - t_s
    first_throughput = first_chunk_size_bit / duration if duration > 0 else 0
    print(f"first_throughput: {first_throughput} bytes/sec")

    if check_video_not_found(first_chunk):
        client_socket.close()
        return

    # create temporary directory if not exist
    if not os.path.exists("tmp"):
        os.makedirs("tmp")

    # write chunk to the temporary directory
    chunk_filepath = os.path.join("tmp", "chunk_0.m4s")
    with open(chunk_filepath, "wb") as f:
        f.write(first_chunk)

    print(f"successfully received the first chunk  at {chunk_filepath}")
    # put the path of the chunk to the queue
    # chunks_queue.put(chunk_filepath)

    # request and receive the rest of the chunks
    request_rest_chunk(client_socket, video_name, first_throughput, num_chunks, sorted_bitrates, alpha)

    client_socket.close()



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

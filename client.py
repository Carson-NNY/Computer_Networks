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

init_connect_t = None

def log_chunk(duration, throughput, avg_throughput, bitrate, video_name, idx):

    global init_connect_t
    cur_time = time.time()
    time_log = cur_time - init_connect_t
    # Format chunk name as in the example: e.g., bunny-292312-00000.m4s
    chunkname = f"{video_name}-{bitrate}-{idx:05d}.m4s"
    log_line = f"{time_log} {duration} {throughput} {avg_throughput} {bitrate} {chunkname}\n"
    with open("log.txt", "a") as f:
        f.write(log_line)

def get_chunk(client_socket, video_name, bitrate, idx):

    chunk_request = f"{video_name} {bitrate} {idx}"
    t_s = time.time()
    client_socket.sendall(chunk_request.encode())

    chunk_data, data_size_bit = receive_data(client_socket)
    if chunk_data is None:
        return None, 0, 0

    t_f = time.time()
    duration = t_f - t_s
    throughput = data_size_bit / duration if duration > 0 else 0
    return chunk_data, throughput, duration


def save_chunk(chunk, idx, chunks_queue):
    """
    Saves the chunk to a temp dir.
    """

    chunk_filepath = os.path.join("tmp", f"chunk_{idx}.m4s")
    with open(chunk_filepath, "wb") as f:
        f.write(chunk)
    # chunks_queue.put(chunk_filepath)

def request_rest_chunk(client_socket, video_name, initial_throughput, num_chunks, sorted_bitrates, alpha, chunks_queue):
    """
    Requests and receives the rest of the chunks from the server.
    Uses a helper function to handle the request and timing for each chunk.
    """
    avg_throughput = initial_throughput

    for i in range(1, num_chunks):
        # Determine the bitrate for this chunk based on the current EWMA throughput estimate.
        bitrate = sorted_bitrates[0]
        for bit in reversed(sorted_bitrates):
            if avg_throughput >= 1.5 * bit:
                bitrate = bit
                break

        chunk_data, cur_throughput, duration = get_chunk(client_socket, video_name, bitrate, i)
        if chunk_data is None:
            print(f"Failed to receive chunk {i}.")
            return

        # Update the throughput using the EWMA formula.
        avg_throughput = alpha * cur_throughput + (1 - alpha) * avg_throughput
        log_chunk(duration, cur_throughput, avg_throughput, bitrate, video_name, i)
        save_chunk(chunk_data, i, chunks_queue)


def receive_data(clientSocket):
    """
    Receives the manifest/video file from the server and returns it as a decoded string.
    """

    file_existed = clientSocket.recv(1)
    if not file_existed or file_existed == b"0":
        print("video not found")
        clientSocket.close()
        return None, None

    file_size = clientSocket.recv(4)
    if not file_size:
        print("video not found")
        clientSocket.close()
        return None, None

    data_size_byte = struct.unpack("!I", file_size)[0]
    data_size_bit = data_size_byte * 8
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

    global init_connect_t
    # create a socket and connect to the server
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_addr, server_port))
    init_connect_t = time.time()

    # send the video name to request the manifest file
    # client_socket.send(video_name.encode())
    manifest_request = f"manifest.mpd {video_name}"
    client_socket.send(manifest_request.encode())

    mani_file, mani_size_bit = (receive_data(client_socket))
    if mani_file is None:
        return

    mani_file = mani_file.decode(errors="replace").strip()

    # Check if the received response is empty
    if not mani_file:
        print("No data received from server.")
        return

    # parse the manifest file
    num_chunks, lowest_bitrate, sorted_bitrates = parse_manifest(mani_file)
    if num_chunks is None or lowest_bitrate is None:
        print("Failed to parse manifest.")
        return

    # Request the first chunk with the lowest bitrate
    first_chunk, first_throughput, duration = get_chunk(client_socket, video_name, lowest_bitrate, 0)
    if first_chunk is None:
        print("Failed to receive first chunk.")
        return

    log_chunk(duration, first_throughput, first_throughput, lowest_bitrate, video_name, 0)
    # create temporary directory if not exist
    if not os.path.exists("tmp"):
        os.makedirs("tmp")
    save_chunk(first_chunk, 0, chunks_queue)

    # request and receive the rest of the chunks
    request_rest_chunk(client_socket, video_name, first_throughput, num_chunks, sorted_bitrates, alpha, chunks_queue)

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

#
# Columbia University - CSEE 4119 Computer Networks
# Assignment 1 - Adaptive video streaming
#
# client.py - the client program for sending requests to the server and playing video chunks
#

import threading
from queue import Queue
import sys
import socket
import os
import xml.etree.ElementTree as parser
import struct
import cv2

init_connect_t = None

def log_chunk(duration, throughput, avg_throughput, bitrate, video_name, idx):
    """
    Logs the chunk download details in log.txt.

    Args:
        duration (float): Time taken to download the chunk.
        throughput (float): Throughput for this chunk.
        avg_throughput (float): EWMA throughput estimate.
        bitrate (int): Bitrate of the chunk.
        video_name (str): Name of the video.
        idx (int): Chunk index.
    """
    global init_connect_t
    cur_time = cv2.getTickCount()
    time_log = (cur_time - init_connect_t) / cv2.getTickFrequency()
    chunkname = f"{video_name}-{bitrate}-{idx:05d}.m4s"
    log_line = f"{time_log} {duration} {throughput} {avg_throughput} {bitrate} {chunkname}\n"
    with open("log.txt", "a") as f:
        f.write(log_line)

def get_chunk(client_socket, video_name, bitrate, idx):
    """
    Requests a video chunk from the server and measures download time.

    Args:
        client_socket (socket): Active socket connection to the server.
        video_name (str): Name of the video.
        bitrate (int): Bitrate of the requested chunk.
        idx (int): Chunk index.

    Returns:
        tuple: (chunk_data (bytes), throughput (float), duration (float))
    """
    chunk_request = f"{video_name} {bitrate} {idx}"
    t_s = cv2.getTickCount()
    client_socket.sendall(chunk_request.encode())

    chunk_data, data_size_bit = receive_data(client_socket)
    if chunk_data is None:
        return None, 0, 0

    t_f = cv2.getTickCount()
    duration = (t_f - t_s) / cv2.getTickFrequency()
    throughput = data_size_bit / duration if duration > 0 else 0
    return chunk_data, throughput, duration

def save_chunk(chunk, idx, chunks_queue):
    """
    Saves the downloaded chunk to a temporary directory.

    Args:
        chunk (bytes): Video chunk data.
        idx (int): Chunk index.
        chunks_queue (Queue): Queue for passing chunk paths to the player.

    Returns:
        None
    """
    chunk_filepath = os.path.join("tmp", f"chunk_{idx}.m4s")
    with open(chunk_filepath, "wb") as f:
        f.write(chunk)

def request_rest_chunk(client_socket, video_name, initial_throughput, num_chunks, sorted_bitrates, alpha, chunks_queue):
    """
    Requests and downloads the remaining video chunks based on adaptive bitrate selection.

    Args:
        client_socket (socket): Active socket connection to the server.
        video_name (str): Name of the video to request.
        initial_throughput (float): Measured throughput from the first chunk.
        num_chunks (int): Total number of chunks in the video.
        sorted_bitrates (list[int]): List of available bitrates in ascending order.
        alpha (float): Alpha value for the EWMA throughput estimation.
        chunks_queue (Queue): Queue for passing chunk file paths to the video player.
    """
    avg_throughput = initial_throughput

    for i in range(1, num_chunks):
        bitrate = sorted_bitrates[0]
        for bit in reversed(sorted_bitrates):
            if avg_throughput >= 1.5 * bit:
                bitrate = bit
                break

        chunk_data, cur_throughput, duration = get_chunk(client_socket, video_name, bitrate, i)
        if chunk_data is None:
            print(f"Failed to receive chunk {i}.")
            return

        avg_throughput = alpha * cur_throughput + (1 - alpha) * avg_throughput
        log_chunk(duration, cur_throughput, avg_throughput, bitrate, video_name, i)
        save_chunk(chunk_data, i, chunks_queue)

def receive_data(clientSocket):
    """
    Receives data from the server, handling both manifest and chunk files.

    Args:
        clientSocket (socket): Active socket connection to the server.

    Returns:
        tuple: (data (bytes), data_size_bit (int)) or (None, None) if failed.
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
        data = clientSocket.recv(min(4096, data_size_byte - len(res)))
        if not data:
            break
        res += data

    return res, data_size_bit

def parse_manifest(mani_file):
    """
    Parses the manifest XML and extracts chunk and bitrate details.

    Args:
        mani_file (str): XML manifest file content.

    Returns:
        tuple: (num_chunks (int), lowest_bitrate (int), sorted_bitrates (list[int])) or (None, None, None) if parsing fails.
    """
    try:
        root = parser.fromstring(mani_file)
        media_presentation_duration = float(root.attrib.get("mediaPresentationDuration", 0))
        max_segment_duration = float(root.attrib.get("maxSegmentDuration", 1))
        num_chunks = int(media_presentation_duration / max_segment_duration)

        representation_elements = root.findall(".//Representation")
        bitrates = [int(rep.get("bandwidth")) for rep in representation_elements if rep.get("bandwidth") is not None]
        sorted_bitrates = sorted(bitrates)
        return num_chunks, sorted_bitrates[0], sorted_bitrates

    except parser.ParseError:
        print("Error parsing manifest XML.")
        return None, None, None

def client(server_addr, server_port, video_name, alpha, chunks_queue):
    """
    Connects to the server, retrieves the manifest file, and downloads video chunks.

    Args:
        server_addr (str): Server IP address or hostname.
        server_port (int): Server port number.
        video_name (str): Name of the video to request.
        alpha (float): Alpha value for the EWMA throughput estimation.
        chunks_queue (Queue): Queue for passing chunk file paths to the video player.
    """
    global init_connect_t
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_addr, server_port))
    init_connect_t = cv2.getTickCount()

    manifest_request = f"manifest.mpd {video_name}"
    client_socket.send(manifest_request.encode())

    mani_file, mani_size_bit = receive_data(client_socket)
    if mani_file is None:
        return

    mani_file = mani_file.decode(errors="replace").strip()
    num_chunks, lowest_bitrate, sorted_bitrates = parse_manifest(mani_file)

    first_chunk, first_throughput, duration = get_chunk(client_socket, video_name, lowest_bitrate, 0)
    log_chunk(duration, first_throughput, first_throughput, lowest_bitrate, video_name, 0)

    if not os.path.exists("tmp"):
        os.makedirs("tmp")
    save_chunk(first_chunk, 0, chunks_queue)

    request_rest_chunk(client_socket, video_name, first_throughput, num_chunks, sorted_bitrates, alpha, chunks_queue)

    client_socket.close()

# Parse input arguments and pass to the client function
if __name__ == '__main__':
    server_addr = sys.argv[1]
    server_port = int(sys.argv[2])
    video_name = sys.argv[3]
    alpha = float(sys.argv[4])

    # Init queue for passing the path of the chunks to the video player
    chunks_queue = Queue()
    # Start the client thread with the input arguments
    client_thread = threading.Thread(target=client, args=(server_addr, server_port, video_name, alpha, chunks_queue))
    client_thread.start()
    # Start the video player
    # play_chunks(chunks_queue)  # Commented out but should work when needed

# CSEE 4119 Spring 2025, Assignment 1
## Guanhong Liu
## GitHub username: Carson-NNY

This project implements an adaptive video streaming system using a client-server architecture. 

## steps to execute the program:

### Installation Guide:

To set up the environment for running the project, follow these installation steps.

**Prerequisites**
Having **Python 3** installed on your system.

**Required Dependencies**
### **1. Install Python Package Manager (pip)**
If `pip` is not installed, install it first.
```sh
sudo apt-get update
sudo apt install python3-pip
pip install opencv-python
sudo apt install libgl1-mesa-glx
```
### 1. Start the server
```sh
python3 server.py 60000
```

### 2. Start the network simulator
```sh
python3 network.py 50000 127.0.0.1 60000 lab1_bw.txt 0.05
```

### 3. Start the client
```sh
python3 client.py 127.0.0.1 50000 bunny 0.2
```

## Assumptions
- The server stores videos in a `data/` directory with videos with corresponding bitratrs.
- a band width file is provided

## Corner Cases
- **Invalid video requests** 
- **Invalid chunk requests**
- **Abrupt disconnections** 

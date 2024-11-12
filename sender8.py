import customtkinter as ctk
from tkinter import messagebox
import pyaudio
import socket
import threading
import time
import os
import json

def get_config_file_path(app_name):
    appdata_path = os.getenv('APPDATA')
    config_dir = os.path.join(appdata_path, app_name)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    config_file = os.path.join(config_dir, 'config.json')
    return config_file

def save_config(app_name, config_data):
    config_file = get_config_file_path(app_name)
    with open(config_file, 'w') as f:
        json.dump(config_data, f)

def load_config(app_name):
    config_file = get_config_file_path(app_name)
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            return json.load(f)
    return None

# Function to list audio devices
def list_audio_devices():
    audio = pyaudio.PyAudio()
    device_count = audio.get_device_count()
    devices = []
    for i in range(device_count):
        device_info = audio.get_device_info_by_index(i)
        devices.append({
            'index': i,
            'name': device_info['name'],
            'max_input_channels': device_info['maxInputChannels'],
            'max_output_channels': device_info['maxOutputChannels'],
        })
        print(f"Device {i}: {device_info}")
    audio.terminate()
    return devices

# Function to find device index by name
def find_device_index_by_name(name, devices):
    for device in devices:
        if device['name'] == name:
            return device['index']
    return None

# Function to start streaming audio from multiple devices
def start_streaming(ip, port, device_names, device_channels, mic_device_name):
    FORMAT = pyaudio.paInt16
    RATE = 44100
    CHUNK = 1024

    audio = pyaudio.PyAudio()
    streams = []
    sockets = []

    devices = list_audio_devices()
    device_indices = [find_device_index_by_name(name, devices) for name in device_names]
    mic_device_index = find_device_index_by_name(mic_device_name, devices)

    try:
        # Open streams for each selected device
        for device_index, channels in zip(device_indices, device_channels):
            print(f"Trying to open stream with device_index={device_index}, channels={channels}, rate={RATE}")
            stream = audio.open(format=FORMAT, channels=channels,
                                rate=RATE, input=True,
                                input_device_index=device_index,
                                frames_per_buffer=CHUNK)
            streams.append(stream)
            print(f"Audio stream opened successfully for device_index={device_index}")

        # Set up socket connections for each stream
        for i in range(len(device_indices)):
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.bind(('0.0.0.0', port + i))
            server_socket.listen(1)
            print(f"Waiting for connection on port {port + i}...")
            conn, addr = server_socket.accept()
            print(f"Connected by {addr} on port {port + i}")
            sockets.append(conn)

        # Start listening for the microphone stream from the receiver
        mic_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        mic_socket.bind(('0.0.0.0', port + len(device_indices)))
        mic_socket.listen(1)
        print(f"Waiting for microphone connection on port {port + len(device_indices)}...")
        mic_conn, mic_addr = mic_socket.accept()
        print(f"Microphone connected by {mic_addr}")

        def receive_mic():
            mic_stream = audio.open(format=FORMAT, channels=1,  # default to 1 channel, can adjust as needed
                                    rate=RATE, output=True,
                                    output_device_index=mic_device_index,
                                    frames_per_buffer=CHUNK)
            try:
                while True:
                    data = mic_conn.recv(CHUNK)
                    if not data:
                        break
                    mic_stream.write(data)
            except Exception as e:
                print(f"Error while receiving microphone data: {e}")
            finally:
                mic_stream.stop_stream()
                mic_stream.close()
                mic_conn.close()
                mic_socket.close()

        threading.Thread(target=receive_mic).start()

        # Stream audio from each device
        try:
            while True:
                for i, stream in enumerate(streams):
                    data = stream.read(CHUNK)
                    if not data:
                        print(f"No audio data captured from device_index={device_indices[i]}")
                    else:
                        sockets[i].sendall(data)
                    time.sleep(0.01)  # Add a small delay to prevent high CPU usage
        except Exception as e:
            print(f"Error while streaming: {e}")
        finally:
            for stream in streams:
                stream.stop_stream()
                stream.close()
            for conn in sockets:
                conn.close()
            for server_socket in sockets:
                server_socket.close()
    except Exception as e:
        print(f"Error setting up stream: {e}")
    finally:
        audio.terminate()

# Function to handle start button click
def on_start():
    ip = ip_entry.get()
    port = int(port_entry.get())
    num_devices = int(num_devices_entry.get())
    device_names = [device_names_var[i].get() for i in range(num_devices)]
    device_channels = [int(device_channels_var[i].get()) for i in range(num_devices)]
    mic_device_name = mic_device_var.get()

    # Save configuration
    config_data = {
        "ip": ip,
        "port": port,
        "num_devices": num_devices,
        "device_names": device_names,
        "device_channels": device_channels,
        "mic_device_name": mic_device_name,
    }
    save_config("AudioStreamSender", config_data)

    threading.Thread(target=start_streaming, args=(ip, port, device_names, device_channels, mic_device_name)).start()
    messagebox.showinfo("Info", "Streaming started. Check console for any errors.")

# Load configuration
config_data = load_config("AudioStreamSender")
if config_data is None:
    config_data = {}

# Create the GUI
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("Audio Stream Sender")
root.geometry("500x900")

ctk.CTkLabel(root, text="Receiver IP:").grid(row=0, column=0, padx=10, pady=5, sticky="e")
ctk.CTkLabel(root, text="Port:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
ctk.CTkLabel(root, text="Number of Devices:").grid(row=2, column=0, padx=10, pady=5, sticky="e")

ip_entry = ctk.CTkEntry(root)
port_entry = ctk.CTkEntry(root)
num_devices_entry = ctk.CTkEntry(root)

ip_entry.grid(row=0, column=1, padx=10, pady=5)
port_entry.grid(row=1, column=1, padx=10, pady=5)
num_devices_entry.grid(row=2, column=1, padx=10, pady=5)

if config_data:
    ip_entry.insert(0, config_data.get("ip", ""))
    port_entry.insert(0, config_data.get("port", ""))
    num_devices_entry.insert(0, config_data.get("num_devices", 2))

# List available audio devices
devices = list_audio_devices()

# Add dropdown menus for selecting audio devices and channels
num_devices = 2  # Adjust this number as needed
device_names_var = []
device_channels_var = []
device_menus = []
channel_entries = []

# Create default channels list based on the number of devices
default_device_channels = ['2'] * num_devices

if config_data:
    default_device_channels = config_data.get("device_channels", ['2'] * num_devices)

for i in range(num_devices):
    ctk.CTkLabel(root, text=f"Audio Device {i+1}:").grid(row=3+i*2, column=0, padx=10, pady=5, sticky="e")
    ctk.CTkLabel(root, text=f"Channels {i+1}:").grid(row=3+i*2+1, column=0, padx=10, pady=5, sticky="e")
    device_names_var.append(ctk.StringVar(root))
    device_channels_var.append(ctk.StringVar(root))
    device_names_var[i].set('')  # Default value
    device_channels_var[i].set('2')  # Default to 2 channels

    device_menu = ctk.CTkOptionMenu(root, variable=device_names_var[i], values=[dev['name'] for dev in devices if dev['max_input_channels'] > 0])
    channel_entry = ctk.CTkEntry(root, textvariable=device_channels_var[i])
   
    device_menu.grid(row=3+i*2, column=1, padx=10, pady=5)
    channel_entry.grid(row=3+i*2+1, column=1, padx=10, pady=5)
   
    device_menus.append(device_menu)
    channel_entries.append(channel_entry)

    if config_data:
        device_names = config_data.get("device_names", [''] * num_devices)
        if i < len(device_names):
           device_names_var[i].set(device_names[i])
        device_channels_var[i].set(default_device_channels[i])
# Add dropdown menu for selecting microphone device
ctk.CTkLabel(root, text="Microphone Device:").grid(row=3+num_devices*2, column=0, padx=10, pady=5, sticky="e")
mic_device_var = ctk.StringVar(root)
mic_device_var.set('')  # Default value

mic_device_menu = ctk.CTkOptionMenu(root, variable=mic_device_var, values=[dev['name'] for dev in devices if dev['max_output_channels'] > 0])
mic_device_menu.grid(row=3+num_devices*2, column=1, padx=10, pady=5)

if config_data:
    mic_device_var.set(config_data.get("mic_device_name", ''))

start_button = ctk.CTkButton(root, text="Start", command=on_start)
start_button.grid(row=4+num_devices*2, columnspan=2, pady=10)

# Display available audio devices
device_list_label = ctk.CTkLabel(root, text="Available Audio Devices:")
device_list_label.grid(row=5+num_devices*2, columnspan=2, pady=10)
device_list_text = ctk.CTkTextbox(root, height=200, width=400)
device_list_text.grid(row=6+num_devices*2, columnspan=2, padx=10, pady=5)
device_list_text.insert("end", "\n".join([f"{dev['name']} (Device {dev['index']})" for dev in devices]))
device_list_text.configure(state="disabled")

root.mainloop()
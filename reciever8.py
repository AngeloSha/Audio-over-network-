import customtkinter as ctk
from tkinter import messagebox
import pyaudio
import socket
import threading
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

# Function to start receiving and playing audio from multiple streams
def start_receiving(ip, port, num_devices, device_names, mic_device_name, mic_channels):
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
        # Set up connections for each stream
        for i in range(num_devices):
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((ip, port + i))
            sockets.append(client_socket)

            stream = audio.open(format=FORMAT, channels=2,
                                rate=RATE, output=True,
                                output_device_index=device_indices[i],
                                frames_per_buffer=CHUNK)
            streams.append(stream)
            print(f"Audio stream opened successfully for port {port + i}")

        # Capture microphone input and send it to the sender
        mic_stream = audio.open(format=FORMAT, channels=mic_channels,
                                rate=RATE, input=True,
                                input_device_index=mic_device_index,
                                frames_per_buffer=CHUNK)

        mic_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        mic_socket.connect((ip, port + num_devices))

        def send_mic():
            try:
                while True:
                    data = mic_stream.read(CHUNK)
                    mic_socket.sendall(data)
            except Exception as e:
                print(f"Error while sending microphone data: {e}")
            finally:
                mic_stream.stop_stream()
                mic_stream.close()
                mic_socket.close()

        threading.Thread(target=send_mic).start()

        # Receive and play audio from each stream
        try:
            while True:
                for i, client_socket in enumerate(sockets):
                    data = client_socket.recv(CHUNK)
                    if not data:
                        print(f"No audio data received on port {port + i}")
                        break
                    streams[i].write(data)
        except Exception as e:
            print(f"Error while receiving: {e}")
        finally:
            for stream in streams:
                stream.stop_stream()
                stream.close()
            for client_socket in sockets:
                client_socket.close()
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
    mic_device_name = mic_device_var.get()
    mic_channels = int(mic_channels_entry.get())

    # Save configuration
    config_data = {
        "ip": ip,
        "port": port,
        "num_devices": num_devices,
        "device_names": device_names,
        "mic_device_name": mic_device_name,
        "mic_channels": mic_channels
    }
    save_config("AudioStreamReceiver", config_data)

    threading.Thread(target=start_receiving, args=(ip, port, num_devices, device_names, mic_device_name, mic_channels)).start()
    messagebox.showinfo("Info", "Receiving started. Check console for any errors.")

# Load configuration
config_data = load_config("AudioStreamReceiver")

# Create the GUI
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("Audio Stream Receiver")
root.geometry("500x800")

ctk.CTkLabel(root, text="Sender IP:").grid(row=0, column=0, padx=10, pady=5, sticky="e")
ctk.CTkLabel(root, text="Port:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
ctk.CTkLabel(root, text="Number of Devices:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
ctk.CTkLabel(root, text="Microphone Channels:").grid(row=3, column=0, padx=10, pady=5, sticky="e")

ip_entry = ctk.CTkEntry(root)
port_entry = ctk.CTkEntry(root)
num_devices_entry = ctk.CTkEntry(root)
mic_channels_entry = ctk.CTkEntry(root)

ip_entry.grid(row=0, column=1, padx=10, pady=5)
port_entry.grid(row=1, column=1, padx=10, pady=5)
num_devices_entry.grid(row=2, column=1, padx=10, pady=5)
mic_channels_entry.grid(row=3, column=1, padx=10, pady=5)

if config_data:
    ip_entry.insert(0, config_data["ip"])
    port_entry.insert(0, config_data["port"])
    num_devices_entry.insert(0, config_data["num_devices"])
    mic_channels_entry.insert(0, config_data.get("mic_channels", 1))  # Default to 1 channel if not present

# List available audio devices
devices = list_audio_devices()

# Add dropdown menus for selecting audio output devices
num_devices = 2  # Adjust this number as needed
device_names_var = []
device_menus = []
for i in range(num_devices):
    ctk.CTkLabel(root, text=f"Output Device {i+1}:").grid(row=4+i, column=0, padx=10, pady=5, sticky="e")
    device_names_var.append(ctk.StringVar(root))
    device_names_var[i].set('')  # Default value
    device_menu = ctk.CTkOptionMenu(root, variable=device_names_var[i], values=[dev['name'] for dev in devices if dev['max_output_channels'] > 0])
    device_menu.grid(row=4+i, column=1, padx=10, pady=5)
    device_menus.append(device_menu)

    if config_data:
        device_names = config_data.get("device_names", [''] * num_devices)
        if i < len(device_names):
            device_names_var[i].set(device_names[i])

# Add dropdown menu for selecting microphone device
ctk.CTkLabel(root, text="Microphone Device:").grid(row=4+num_devices, column=0, padx=10, pady=5, sticky="e")
mic_device_var = ctk.StringVar(root)
mic_device_var.set('')  # Default value
mic_device_menu = ctk.CTkOptionMenu(root, variable=mic_device_var, values=[dev['name'] for dev in devices if dev['max_input_channels'] > 0])
mic_device_menu.grid(row=4+num_devices, column=1, padx=10, pady=5)

if config_data:
    mic_device_var.set(config_data.get("mic_device_name", ''))

start_button = ctk.CTkButton(root, text="Start", command=on_start)
start_button.grid(row=5+num_devices, columnspan=2, pady=10)

# Display available audio devices
device_list_label = ctk.CTkLabel(root, text="Available Audio Output Devices:")
device_list_label.grid(row=6+num_devices, columnspan=2, pady=10)
device_list_text = ctk.CTkTextbox(root, height=200, width=400)
device_list_text.grid(row=7+num_devices, columnspan=2, padx=10, pady=5)
device_list_text.insert("end", "\n".join([f"{dev['name']} (Device {dev['index']})" for dev in devices]))
device_list_text.configure(state="disabled")

root.mainloop()

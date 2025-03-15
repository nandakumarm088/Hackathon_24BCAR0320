import json
import google.cloud.dialogflow as dialogflow
import tkinter as tk
from tkinter import scrolledtext
import threading
import os
from google.oauth2 import service_account
import speech_recognition as sr
import pyttsx3  # Text-to-Speech

# Load Dialogflow credentials
CREDENTIALS_PATH = "dialogflow_credentials.json"
credentials = service_account.Credentials.from_service_account_file(CREDENTIALS_PATH)
session_client = dialogflow.SessionsClient(credentials=credentials)
project_id = json.load(open(CREDENTIALS_PATH))['project_id']

# Load devices from JSON
DEVICES_PATH = "devices.json"
with open(DEVICES_PATH, "r") as f:
    devices_data = json.load(f)["devices"]

# Initialize Text-to-Speech engine
tts_engine = pyttsx3.init()
tts_engine.setProperty("rate", 150)  # Adjust speaking speed

# Function to Log Messages
def log_message(message, speak=False):
    log_box.config(state='normal')
    log_box.insert(tk.END, message + "\n")
    log_box.config(state='disabled')
    log_box.yview(tk.END)
    if speak:
        speak_text(message)

# Function to Query Dialogflow
def detect_intent(text):
    session_id = "123456"
    session = session_client.session_path(project_id, session_id)
    query_input = dialogflow.QueryInput(text=dialogflow.TextInput(text=text, language_code="en"))
    response = session_client.detect_intent(session=session, query_input=query_input)
    return response.query_result

# Function to Recognize Speech
def recognize_speech():
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 100
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        start_button.config(text="Listening...", state='disabled')
        log_message("Listening...")
        try:
            audio = recognizer.listen(source, timeout=5)
            text = recognizer.recognize_google(audio)
            log_message(f"You: {text}")
            process_command(text)
        except sr.UnknownValueError:
            log_message("Couldn't understand, please try again.", speak=True)
        except sr.RequestError:
            log_message("Error connecting to speech service.", speak=True)
        except sr.WaitTimeoutError:
            log_message("No speech detected.", speak=True)
    start_button.config(text="Speak", state='normal')


# Function to Process Commands
def process_command(text):
    try:
        response = detect_intent(text)
        fulfillment_text = response.fulfillment_text.strip()
        intent_name = response.intent.display_name if response.intent else "Unknown Intent"

        # Convert MapComposite to a Python dictionary
        params = {key: value for key, value in response.parameters.items()}

        # Check if intent has a registered handler
        if intent_name in intent_handlers:
            fulfillment_text = intent_handlers[intent_name](text, params)
        else:
            fulfillment_text = fulfillment_text or "I'm not sure how to respond to that."

        log_message(f"Assistant: {fulfillment_text}")
        speak_text(fulfillment_text)

    except Exception as e:
        log_message(f"Error: {str(e)}", speak=True)


# Intent Handlers Dictionary
intent_handlers = {}


# 🔹 Register Intent Handler
def register_intent(intent_name):
    def decorator(func):
        intent_handlers[intent_name] = func
        return func
    return decorator


# 🔹 Light ON/OFF Handler
@register_intent("smarthome.lights.switch.on")
@register_intent("smarthome.device.switch.on")
def handle_turn_on(text, params):
    for device in devices_data:
        if device["name"].lower() in text.lower():
            device["status"] = "ON"
            update_device_label(device)
            save_device_data()
            return f"Turning on the {device['name']}."
    return "Which device would you like to turn on?"


@register_intent("smarthome.lights.switch.off")
@register_intent("smarthome.device.switch.off")
def handle_turn_off(text, params):
    for device in devices_data:
        if device["name"].lower() in text.lower():
            device["status"] = "OFF"
            update_device_label(device)
            save_device_data()
            return f"Turning off the {device['name']}."
    return "Which device would you like to turn off?"


# 🔹 Temperature Control Handler
@register_intent("smarthome.heating.set")
def handle_set_temperature(text, params):
    for device in devices_data:
        if "temperature" in device and device.get("status") == "ON":
            final_value = params.get("final-value")
            if isinstance(final_value, (int, float)):
                old_temp = device["temperature"]
                device["temperature"] = int(final_value)
                update_device_label(device)
                save_device_data()
                return f"Setting {device['name']} from {old_temp}°C to {device['temperature']}°C."
            return "Please provide a valid temperature value."
    return "Please turn on the AC before setting the temperature."


@register_intent("smarthome.heating.up")
def handle_increase_temperature(text, params):
    for device in devices_data:
        if "temperature" in device and device.get("status") == "ON":
            change_value = params.get("change-value")
            if isinstance(change_value, (int, float)):
                old_temp = device["temperature"]
                device["temperature"] += int(change_value)
                update_device_label(device)
                save_device_data()
                return f"Increasing {device['name']} from {old_temp}°C to {device['temperature']}°C."
            return "Please provide a valid temperature increment."
    return "Please turn on the heater or AC before adjusting the temperature."


@register_intent("smarthome.heating.down")
def handle_decrease_temperature(text, params):
    for device in devices_data:
        if "temperature" in device and device.get("status") == "ON":
            change_value = params.get("change-value")
            if isinstance(change_value, (int, float)):
                old_temp = device["temperature"]
                device["temperature"] -= int(change_value)
                update_device_label(device)
                save_device_data()
                return f"Decreasing {device['name']} from {old_temp}°C to {device['temperature']}°C."
            return "Please provide a valid temperature decrement."
    return "Please turn on the heater or AC before adjusting the temperature."


# 🔹 Save Updated Device Data
def save_device_data():
    with open(DEVICES_PATH, "w") as f:
        json.dump({"devices": devices_data}, f, indent=4)


# Function to extract temperature value from voice command
def extract_temperature(text):
    words = text.split()
    for word in words:
        if word.isdigit():
            return int(word)  # Return the first number found
    return None



def update_device_label(device):
    device_name_lower = device["name"].lower()
    if device_name_lower in device_labels:
        if "temperature" in device:
            # Display temperature for AC & Heater
            device_labels[device_name_lower].config(
                text=f"{device['name']} is {device['status']} | Temp: {device['temperature']}°C", 
                fg="green" if device["status"] == "ON" else "red"
            )
        else:
            # Standard ON/OFF display
            device_labels[device_name_lower].config(
                text=f"{device['name']} is {device['status']}", 
                fg="green" if device["status"] == "ON" else "red"
            )


# Function to Make Assistant Speak
def speak_text(text):
    tts_engine.say(text)
    tts_engine.runAndWait()

# Function to Send Text Input
def send_text():
    text = text_entry.get()
    if text.strip():
        log_message(f"You: {text}")
        process_command(text)
        text_entry.delete(0, tk.END)

        

# Function to Add a New Device
def add_device():
    new_device_name = device_entry.get().strip()
    
    if not new_device_name or new_device_name == PLACEHOLDERS["device_entry"]:
        log_message("Please enter a valid device name.", speak=True)
        return

    with open(DEVICES_PATH, "r") as f:
        devices_json = json.load(f)

    for device in devices_json["devices"]:
        if device["name"].lower() == new_device_name.lower():
            log_message(f"Device '{new_device_name}' already exists.")
            device_entry.delete(0, tk.END)
            return

    if "light" in new_device_name.lower():
        new_device = {
            "name": new_device_name,
            "status": "OFF",
            "intent_on": "smarthome.lights.switch.on",
            "intent_off": "smarthome.lights.switch.off"
        }
    elif "ac" in new_device_name.lower() or "heater" in new_device_name.lower():
        new_device = {
            "name": new_device_name,
            "status": "OFF",
            "temperature": 24,  # Default temperature
            "intent_on": "smarthome.device.switch.on",
            "intent_off": "smarthome.device.switch.off",
            "intent_temp": "smarthome.temp.set"
        }
    else:
        new_device = {
            "name": new_device_name,
            "status": "OFF",
            "intent_on": "smarthome.device.switch.on",
            "intent_off": "smarthome.device.switch.off"
        }

    devices_json["devices"].append(new_device)

    with open(DEVICES_PATH, "w") as f:
        json.dump(devices_json, f, indent=4)

    log_message(f"Device '{new_device_name}' added successfully.")
    refresh_devices()
    device_entry.delete(0, tk.END)




   

# Function to Remove a Device
def remove_device(device_name):
    global devices_data
    devices_data = [device for device in devices_data if device["name"].lower() != device_name.lower()]
    with open(DEVICES_PATH, "w") as f:
        json.dump({"devices": devices_data}, f, indent=4)
    refresh_devices()     

# Function to Refresh Device UI (Updated to Show Temperature on Load)
def refresh_devices():
    global devices_data
    with open(DEVICES_PATH, "r") as f:
        devices_data = json.load(f)["devices"]
    
    for widget in device_frame.winfo_children():
        widget.destroy()
    
    global device_labels
    device_labels = {}

    for device in devices_data:
        device_container = tk.Frame(device_frame)
        device_container.pack(pady=5, fill="x")
        
        # Determine text color based on device status
        text_color = "green" if device["status"] == "ON" else "red"
        
        # Check if the device has a temperature property
        if "temperature" in device:
            label_text = f"{device['name']} is {device['status']} | Temp: {device['temperature']}°C"
        else:
            label_text = f"{device['name']} is {device['status']}"

        label = tk.Label(device_container, text=label_text, font=("Arial", 14), fg=text_color)
        label.pack(side=tk.LEFT, padx=5)
        device_labels[device["name"].lower()] = label

        remove_button = tk.Button(device_container, text="Remove", command=lambda d=device["name"]: remove_device(d))
        remove_button.pack(side=tk.RIGHT, padx=5)

PLACEHOLDERS = {
    "text_entry": "Use text to talk to the assistant...",
    "device_entry": "Enter name of new device..."
}

def on_focus_in(event):
    if event.widget.get() == PLACEHOLDERS.get(event.widget._name, ""):
        event.widget.delete(0, tk.END)
        event.widget.config(fg='black')  # Change text color to black when user types

def on_focus_out(event):
    if event.widget.get() == "":
        placeholder = PLACEHOLDERS.get(event.widget._name, "")
        event.widget.insert(0, placeholder)
        event.widget.config(fg='gray')  # Keep placeholder text gray

# GUI Setup
root = tk.Tk()
root.title("AI Assistant")
root.update_idletasks()

log_box = scrolledtext.ScrolledText(root, width=60, height=10, state='disabled')
log_box.pack(pady=10)

start_button = tk.Button(root, text="Speak", command=lambda: threading.Thread(target=recognize_speech, daemon=True).start())
start_button.pack(pady=5)

# Text entry
text_entry = tk.Entry(root, width=50, fg='gray', name="text_entry")
text_entry.insert(0, PLACEHOLDERS["text_entry"])
text_entry.bind('<FocusIn>', on_focus_in)
text_entry.bind('<FocusOut>', on_focus_out)
text_entry.pack(pady=5)

send_button = tk.Button(root, text="Ask", command=send_text)
send_button.pack(pady=5)

# Device input section (centered)
device_frame_container = tk.Frame(root)
device_frame_container.pack(pady=5)

device_entry = tk.Entry(device_frame_container, width=30, fg='gray', name="device_entry")
device_entry.insert(0, PLACEHOLDERS["device_entry"])
device_entry.bind('<FocusIn>', on_focus_in)
device_entry.bind('<FocusOut>', on_focus_out)
device_entry.pack(side=tk.LEFT, padx=5)

add_device_button = tk.Button(device_frame_container, text="Add", command=add_device)
add_device_button.pack(side=tk.LEFT)

# Device frame
device_frame = tk.Frame(root)
device_frame.pack(pady=10)

refresh_devices()

root.mainloop()

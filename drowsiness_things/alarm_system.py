import paho.mqtt.client as mqtt
import json
import pygame
import threading
import time
import datetime

host = "broker.hivemq.com"
port = 1883
file_path = "music.wav"  # Path to your WAV file

topic = "----/log/dev_01"
close_count = 0
alarm_status = "0"  # Initialize alarm_status to "0"
stop_music_event = threading.Event()


def on_connect(client, userdata, flags, rc):
    print("MQTT Connected.")
    client.subscribe("----")

def play_wav(file_path):
    pygame.init()
    pygame.mixer.init()
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play(-1)  # Loop indefinitely

    while True:
        stop_music_event.wait()  # Wait until the stop event is set
        pygame.mixer.music.stop()
        stop_music_event.clear()  # Reset the event flag

def on_message(client, userdata, msg):
    global close_count  # Declare close_count as global
    global alarm_status
    msg_payload = msg.payload.decode("utf-8", "strict")
    data = json.loads(msg_payload)
    eye_status = data.get("eye_status")

    if eye_status == "1":
        close_count += 1
        if close_count >= 3:
            print("Alarm On")
            alarm_status = "1"  # Set alarm_status to "1" when alarm is triggered
            timenow = datetime.datetime.now()
            print(timenow)
            threading.Thread(target=play_wav, args=(file_path,)).start()
            stop_music_event.clear()  # Clear the event flag
            publish_message(client, eye_status, alarm_status, str(timenow))
            
        else:
            timenow2 = datetime.datetime.now()
            print(timenow2)
            publish_message(client, eye_status, alarm_status, str(timenow2)) 

    else:
        timenow3 = datetime.datetime.now()
        print(timenow3)
        close_count = 0
        publish_message(client, eye_status, alarm_status, str(timenow3))  # Publish the updated alarm_status

def input_thread():
    global close_count
    global alarm_status
    while True:
        key_input = input()
        if key_input == 'q':
            stop_music_event.set()  # Set the event flag to stop the music
            close_count = 0
            alarm_status = "0"

# Start input thread
threading.Thread(target=input_thread).start()

# Function to publish the message
def publish_message(client, eye_status, alarm_status, timestamp):
    payload = {
        "dev_id": "dev_01",
        "car_driver_id":"cd_01",
        "eye_status": eye_status,
        "alarm_status": alarm_status,
        "timestamp": timestamp
    }
    client.publish(topic, json.dumps(payload))
    print("Published message")

# Start MQTT client
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(host)
client.loop_forever()

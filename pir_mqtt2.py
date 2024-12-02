import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
import os
import subprocess
import time
import json

# GPIO 및 PIR 센서 설정
PIR_PIN = 21
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIR_PIN, GPIO.IN)

# MQTT 설정
BROKER = "192.168.25.55"
PORT = 1883
TOPIC = "sensor/pir/room2"

os.environ["SDL_AUDIODRIVER"] = "alsa"
os.environ["AUDIODEV"] = "hw:2,0"

motion_detected = False
last_motion_time = 0
MOTION_TIMEOUT = 10

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("MQTT 연결 성공!")
        client.subscribe(TOPIC)
    else:
        print(f"MQTT 연결 실패. 코드: {rc}")

def on_message(client, userdata, msg):
    print(f"Received message on topic {msg.topic}: {msg.payload.decode()}")
    try:
        payload = json.loads(msg.payload.decode())
        if "url" in payload:
            url = payload["url"]
            currentTime = payload.get("currentTime", 0)
            print(f"Streaming music from: {url} at {currentTime}s")
            stop_music_ffplay()  # 기존 음악 중지
            play_music_ffplay(url, currentTime)
        elif "stop" in payload:
            print("Stopping music")
            stop_music_ffplay()
    except Exception as e:
        print(f"Error: {e}")

def play_music_ffplay(url, start_time):
    command = [
        "/usr/bin/ffplay",
        "-i", url,
        "-ss", str(start_time),
        "-nodisp",
        "-autoexit"
    ]
    print("Executing command:", " ".join(command))
    try:
        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
    except Exception as e:
        print(f"Error executing ffplay: {e}")

def stop_music_ffplay():
    try:
        subprocess.run(["pkill", "-f", "ffplay"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Stopped ffplay process.")
    except Exception as e:
        print(f"Error stopping ffplay: {e}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

try:
    print("PIR 센서를 모니터링 중...")
    client.connect(BROKER, PORT, 60)
    client.loop_start()
    print("MQTT connect try")

    while True:
        if GPIO.input(PIR_PIN): 
            if not motion_detected:
                print("모션 감지됨!")
                client.publish(TOPIC, "motionDetected", qos=2)
                motion_detected = True
            last_motion_time = time.time()
        else:
            if motion_detected and (time.time() - last_motion_time > MOTION_TIMEOUT):
                print("모션 없음 20초 이상 지속")
                client.publish(TOPIC, "motionStopped", qos=2)
                print("모션 없음 보내기 성공")
                motion_detected = False

        time.sleep(1)

except KeyboardInterrupt:
    print("프로그램 종료")
finally:
    GPIO.cleanup()
    client.disconnect()
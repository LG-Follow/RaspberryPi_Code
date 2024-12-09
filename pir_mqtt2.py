import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
import os
import time
import json
import vlc

# GPIO 및 PIR 센서 설정
PIR_PIN = 21
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIR_PIN, GPIO.IN)

# MQTT 설정
BROKER = "BROKER_IP"
PORT = 1883
TOPIC = "sensor/pir/room2"

# VLC 플레이어 초기화
class VLCPlayer:
    def __init__(self):
        self.instance = vlc.Instance("--aout", "alsa", "--alsa-audio-device=hw:2,0")
        self.player = self.instance.media_player_new()
        self.current_url = None
        self.current_time = 0

    def play(self, url, start_time):
        if self.current_url != url:  # URL이 변경된 경우에만 새 미디어 로드
            media = self.instance.media_new(url)
            self.player.set_media(media)
            self.current_url = url

        self.player.play()
        time.sleep(0.1)  # VLC가 준비될 때까지 대기
        self.player.set_time(int(start_time * 1000))  # 특정 시점으로 이동
       # print(f"Playing music from {url} at {start_time}s")

    def set_time(self, start_time):
        self.player.set_time(int(start_time * 1000))

    def pause(self):
        self.player.pause()  # VLC에서 일시 정지
        print("Music paused.")

    def set_volume(self, volume):
        self.player.audio_set_volume(volume) 
vlc_player = VLCPlayer()

# 모션 감지 상태 변수
motion_detected = False
last_motion_time = 0
MOTION_TIMEOUT = 10

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        #print("MQTT 연결 성공")
        print("""
     [MQTT 연결]
+------------------+
|    CONNECTION    |
|     SUCCESS!     |
|  --------------  |
|   STATUS: ✔      |
|                  |
|  Broker: ACTIVE  |
+------------------+

** MQTT 연결 성공! **
""")

        client.subscribe(TOPIC)
    else:
        print(f"MQTT 연결실패. code: {rc}")

def on_message(client, userdata, msg):
    #print(f"Received message on topic {msg.topic}: {msg.payload.decode()}")
    try:
        payload = json.loads(msg.payload.decode())
        if "url" in payload:
            url = payload["url"]
            current_time = payload["currentTime"]
            server_time = payload["timestamp"]
            initial = payload["initial"]

            # 서버-클라이언트 간 시간 차이를 보정
            delay = (time.time() * 1000) - server_time
            current_time += (delay / 1000)

            if initial:
                vlc_player.play(url, current_time)
                vlc_player.set_volume(0)
            else:
                print(f"""
      ♪ ♪ ♪
  {current_time}부터 음악 재생시작)
+----------------+
|                |
|      *****     |
|    *       *   |
|   *         *  |
|    *       *   |
|      *****     |
|                |
|      *****     |
|    *       *   |
|   *         *  |
|    *       *   |
|      *****     |
|                |
+----------------+
     ♪ ♪ ♪
""")

                if vlc_player.current_url == url:
                    # URL이 동일하다면 기존 객체에서 시점 변경
                    vlc_player.set_time(current_time)
                else:
                    # URL이 변경되었다면 새로 재생
                    vlc_player.play(url, current_time)
                vlc_player.set_volume(100)

        elif "stop" in payload:
            print("""
     [음악 꺼짐]
+----------------+
|      X    X    |
|       X  X     |
|        XX      |
|       X  X     |
|      X    X    |
|                |
|      X    X    |
|       X  X     |
|        XX      |
|       X  X     |
|      X    X    |
|                |
+----------------+
   ** 음악이 꺼졌습니다 **
""")

            vlc_player.set_volume(0) 
    except json.JSONDecodeError:
        pass

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

try:
    print("""
+----------------+
|                |
|      *****     |
|    *       *   |
|   *         *  |
|    *       *   |
|      *****     |
|                |
|      *****     |
|    *       *   |
|   *         *  |
|    *       *   |
|      *****     |
|                |
+----------------+
""")

    print("Speaker's PIR sensor monitoring")
    client.connect(BROKER, PORT, 60)
    client.loop_start()
    while True:
        if GPIO.input(PIR_PIN):  # 모션 감지됨
            if not motion_detected:
                print("""
            [PIR 센서]
            +--------+
            | MOTION |
            | Detect |
            +--------+
            """)
                client.publish(TOPIC, "motionDetected", qos=1)
                motion_detected = True
            last_motion_time = time.time()
        else:
            if motion_detected and (time.time() - last_motion_time > MOTION_TIMEOUT):
                print("""
            [PIR 센서]
            +--------+
            | MOTION |
            |  Stop  |
            |for 10s |
            +--------+
            """)
                client.publish(TOPIC, "motionStopped", qos=1)
                print(".      motionStopped 서버로 전송")
                motion_detected = False

        time.sleep(1)

except KeyboardInterrupt:
    print("프로그램 종료")
finally:
    GPIO.cleanup()
    client.disconnect()
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
BROKER = "192.168.25.38"
PORT = 1883
TOPIC = "sensor/pir/room1"

# VLC 플레이어 초기화
class VLCPlayer:
    def __init__(self):
        self.instance = vlc.Instance("--aout", "alsa")
        self.player = self.instance.media_player_new()
        self.current_url = None
        self.current_time = 0

    def play(self, url, start_time):
        if self.current_url != url:  # URL이 변경된 경우에만 새 미디어 로드
            media = self.instance.media_new(url)
            self.player.set_media(media)
            self.current_url = url

        self.player.play()
        time.sleep(0.5)  # VLC가 준비될 때까지 대기
        self.player.set_time(int(start_time * 1000))  # 특정 시점으로 이동
        print(f"Playing music from {url} at {start_time}s")

    def set_time(self, start_time):
        self.player.set_time(int(start_time * 1000))

    def pause(self):
        self.player.pause()  # VLC에서 일시 정지
        print("Music paused.")

    def set_volume(self, volume):
        self.player.audio_set_volume(volume)  # VLC 볼륨 설정
        print(f"Set volume to {volume}%.")

vlc_player = VLCPlayer()

# 모션 감지 상태 변수
motion_detected = False
last_motion_time = 0
MOTION_TIMEOUT = 20

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
            current_time = payload["currentTime"]
            server_time = payload["timestamp"]
            initial = payload["initial"]

            # 서버-클라이언트 간 시간 차이를 보정
            delay = (time.time() * 1000) - server_time
            current_time += (delay / 1000)

            print(f"Streaming music from: {url} at {current_time}s")
            if initial:
                # initial: true일 경우 볼륨 0으로 설정하고 재생
                vlc_player.play(url, current_time)
                vlc_player.set_volume(0)
            else:
                if vlc_player.current_url == url:
                    # URL이 동일하다면 기존 객체에서 시점 변경
                    vlc_player.set_time(current_time)
                else:
                    # URL이 변경되었다면 새로 재생
                    vlc_player.play(url, current_time)
                vlc_player.set_volume(50)
           # vlc_player.play(url, current_time)
           # vlc_player.set_volume(100)  # 볼륨 최대치로 설정

        elif "stop" in payload:
            print("Stopping music")
            vlc_player.set_volume(0)  # 볼륨을 0으로 줄임 (음악 끈 것처럼 처리)
    except Exception as e:
        print(f"Error: {e}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

try:
    print("PIR 센서를 모니터링 중...")
    client.connect(BROKER, PORT, 60)
    client.loop_start()
    print("MQTT connect try")

    while True:
        if GPIO.input(PIR_PIN):  # 모션 감지됨
            if not motion_detected:
                print("모션 감지됨!")
                client.publish(TOPIC, "motionDetected", qos=1)
                motion_detected = True
            last_motion_time = time.time()
        else:
            if motion_detected and (time.time() - last_motion_time > MOTION_TIMEOUT):
                print("모션 없음 20초 이상 지속")
                client.publish(TOPIC, "motionStopped", qos=1)
                print("모션 없음 보내기 성공")  # 볼륨을 0으로 줄임
                motion_detected = False

        time.sleep(1)

except KeyboardInterrupt:
    print("프로그램 종료")
finally:
    GPIO.cleanup()
    client.disconnect()
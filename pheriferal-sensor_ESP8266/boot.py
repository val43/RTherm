HOST = "ESP8266-sensor"

WIFI_SSID = 'DunderMifflin'
WIFI_PSWD = 'PropertyOfDwight'
WIFI_GTWY = '192.168.1.1'

mqtt_server = '192.168.1.210'
mqtt_port = 1883
mqtt_user = "mosca"
mqtt_pswd = "6unoSpasso"
client_ID = "RTherm_sensor_out1"
#MQTT_REFRESH_DELAY = See below!
TOPICS_PUB = {'readings':'thermostat/readings'}

import sys,gc,machine,micropython,esp #,uos
import json, time, network
import umqttsimple, webrepl, BME280
from ntptime import settime
RTC_TIMEZONE_OFFSET = 1
esp.osdebug(None)
#from ubinascii import hexlify
#client_ID = hexlify(machine.unique_id())


# ESP8266 - Pin assignment
i2c = machine.I2C(scl=machine.Pin(5, machine.Pin.OPEN_DRAIN), sda=machine.Pin(4, machine.Pin.OPEN_DRAIN), freq=10000)
LEDPin = machine.Pin(16, machine.Pin.OUT)

# TIMERS
LOOP_DELAY = micropython.const(59.9) #secondi

blindmode = False
blind_cycles_countdown = 3
got_NTP = False



def tf_echo(area,msg):
    global got_NTP
    if got_NTP:
        localtime = time.localtime(time.time())
        msg = "{:02d}:{:02d}:{:02d}  {}: {}".format(localtime[3],localtime[4],localtime[5], area, msg)
    else:
        msg = "--:--:--  {}: {}".format(area, msg)
    print(msg)
    return msg


def wlan_connect():
    print('waiting for connection...')
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(dhcp_hostname=HOST)
    wlan.connect(WIFI_SSID, WIFI_PSWD)
    while not wlan.isconnected():
        machine.idle()
    print('...connected. network config:', wlan.ifconfig())


# NTP
def try_NTP():
    global RTC_TIMEZONE_OFFSET
    try:
        # scrivi NTP su RTC
        settime()
        tm = time.localtime()
        tm = tm[0:3] + (0,) + (tm[3] + RTC_TIMEZONE_OFFSET,) + tm[4:6] + (0,)
        machine.RTC().datetime(tm)
        return True
    except:
        tf_echo("SYS","unable to get the time from the internet...")
        return False
        


#esp.osdebug(None)
wlan_connect()
got_NTP = try_NTP()
LEDPin.off()


# webREPL
try:
    webrepl.start()
except Exception as e:
    tf_echo('Failed to load webREPL with error {}'.format(e))


# TEST BME 280
try:
    bme = BME280.BME280(i2c=i2c)
except Exception as e:
    tf_echo("SYS","connection to local BME280 sensor has failed with error: {}".format(e))
    tf_echo("SYS","Running in blind mode. The device will be shut down within {} cycles.".format(blind_cycles_countdown))
    blindmode = True


gc.collect()

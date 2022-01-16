# ispirato a: https://RandomNerdTutorials.com

# LIBRARIES
import sys, gc, machine, micropython, json, time, network, webrepl, umqttsimple, BME280
#import esp, uos, usocket
from ds3231_port import DS3231
from ntptime import settime

#from ubinascii import hexlify
#client_ID = hexlify(machine.unique_id())
gc.collect()


HOST = "ESP32-thermostat"

WIFI_SSID = 'DunderMifflin'
WIFI_PSWD = 'PropertyOfDwight'
WIFI_GTWY = '192.168.1.1'

mqtt_server = '192.168.1.210'
mqtt_port = 1883
mqtt_user = "mosca"
mqtt_pswd = "6unoSpasso"
client_ID = "RTherm_main"
TOPICS_SUB = { 'readings': 'thermostat/readings' }
# MSG_READINGS = 'thermostat/readings'
# MSG_ACK =      'thermostat/ack'
# MSG_CONSOLE =  'thermostat/console'

COM_TOPICS = ["ACK", "LOG", "THERM", "MSR", "CMD", "TIME"]

RTC_TIMEZONE_OFFSET = 1



# Pin assignment
#pin_rx = 16 #default UART 2
#pin_tx = 17 #default UART 2

pin_heat = machine.Pin(12, machine.Pin.OUT) #D12 (adc2-5, touch5, hspi-q)
pin_heat.off()

pin_cool = machine.Pin(27, machine.Pin.OUT) #D27 (adc2-7, touch7)
pin_cool.off()

LEDPin = machine.Pin(14, machine.Pin.OUT) #D14 (adc2-6, touch6, hspi-clk)

pin_i2c_sda = 21
pin_i2c_scl = 22
i2c = machine.I2C(scl=machine.Pin(pin_i2c_scl,machine.Pin.OPEN_DRAIN), \
                    sda=machine.Pin(pin_i2c_sda, machine.Pin.OPEN_DRAIN), \
                    freq=10000)



# FAILSAFE
PARAMETRI = {"estate": {"minima":   micropython.const(18), \
                        "massima":  micropython.const(28), \
                        "diff_max": micropython.const(6), \
                        "isteresi": 0.8, # innesca 0.4C sopra il target, si ferma 0.4C sotto  \
                        "macchina": "condizionatore" }, \
            "inverno": {"minima":   micropython.const(15), \
                        "massima":  micropython.const(25), \
                        "isteresi": 0.8, # innesca 0.4C sotto il target, si ferma 0.4C sopra \
                        "macchina": "caldaia" }, \
            "off":      None }

MACCHINE = {"caldaia": {"pin":    pin_heat, \
                        "act":    "Riscaldamento", \
                        "status": 0 }, \
            "condizionatore": {"pin":    pin_cool, \
                               "act":    "Raffrescamento", \
                               "status": 0 }}
#             "heatpump": {}} \

STATUS_LBL = ["OFF", "ON"]
OUTSIDE = {}


got_RTC = False #se non conosciamo l'orario corretto, non comunichiami dati termici a RPI
got_NTP = False
ds3231 = None

blindmode = False #se non abbiamo sensori, non accendiamo nulla
blind_cycles_countdown = 3 #per quanti cicli lavorare prima di spegnere tutto


# TIMERS
THERM_REFRESH_DELAY = micropython.const(30000) #millisecondi = 30s
NTP_SYNC_DELAY =      micropython.const(43200000) #millisecondi = 12h
RTC_SYNC_DELAY =      micropython.const(3600000) #millisecondi = 1h
UART_REFRESH_DELAY =  micropython.const(900) #millisecondi = 1s
LOOP_DELAY =          micropython.const(1000) #millisecondi = 1s
MQTT_REFRESH_DELAY =  micropython.const(30000) #millisecondi = 30s



# FUNCTIONS
def tf_echo(area,msg):
    global got_RTC, got_NTP
    if got_RTC or got_NTP:
        localtime = time.localtime(time.time())
        msg = "{:02d}:{:02d}:{:02d}  {}: {}".format(localtime[3],localtime[4],localtime[5], area, msg)
    else:
        msg = "--:--:--  {}: {}".format(area, msg)
    print(msg)
    return msg

    
def wlan_connect():
    tf_echo("SYS","waiting for connection...")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(dhcp_hostname=HOST)
    wlan.connect(WIFI_SSID, WIFI_PSWD)
    while not wlan.isconnected():
        machine.idle()
    tf_echo("SYS","...connected. network config: {}".format(wlan.ifconfig()))


def try_RTC(i2c):
    global ds3231
    try:
        ds3231 = DS3231(i2c)
        return True
        
    except Exception as e:
        tf_echo("SYS","failed to retrieve the local time from RTC with error: {}".format(e))
        return False
    

def try_NTP(got_RTC, RTC_TIMEZONE_OFFSET):
    global ds3231
    try:
        # scrivi NTP su RTC
        settime()
        tm = time.localtime()
        tm = tm[0:3] + (0,) + (tm[3] + RTC_TIMEZONE_OFFSET,) + tm[4:6] + (0,)
        #print(tm)
        machine.RTC().datetime(tm)
        if got_RTC:
            ds3231.save_time()
            #print(ds3231.get_time())
        return True
    
    except Exception as e:
        tf_echo("SYS","unable to get the time from the internet, because: {}".format(e))
        return False
    

def uart_send(topic, msg):
    global COM_TOPICS
    
    if not topic in COM_TOPICS:
        return "ERROR: unknown topic."
    
    sendme = {"topic": topic, "data": msg}
    try:
        uart.write(json.dumps(sendme)+"\n")
    except Exception as e:
        return e
    
    return "Successfully sent data"




# INIT
#esp.osdebug(None)
LEDPin.on()

if machine.reset_cause() == machine.DEEPSLEEP_RESET:
    tf_echo("SYS","booted from deep sleep")
else:
    tf_echo("SYS","booted after power-on or hard reset")
    

wlan_connect()
got_RTC = try_RTC(i2c)
got_NTP = try_NTP(got_RTC, RTC_TIMEZONE_OFFSET)


# UART
try:
    uart = machine.UART(2, 9600)
    # DEFAULT UART(2, baudrate=9600, bits=8, parity=None, stop=1, tx=17, rx=16, rts=-1, cts=-1, txbuf=256, rxbuf=256, timeout=0, timeout_char=2)
    uart.init(baudrate=9600, bits=8, parity=None, stop=1) #tx=pin_tx, rx=pin_rx, 
    
except Exception as e:
    tf_echo("SYS","initialization of serial connection has failed with error: {}".format(e))


# BME280
try:
    bme = BME280.BME280(i2c=i2c)
    
except Exception as e:
    bme = None
    tf_echo("SYS","connection to local BME280 sensor has failed with error: {}".format(e))
    tf_echo("SYS","Running in blind mode. The device will be shut down within {} cycles.".format(blind_cycles_countdown))
    blindmode = True
    

# webREPL
try:
    webrepl.start()
except Exception as e:
    tf_echo("SYS","webREPL failed with error {}.".format(e))

gc.collect()


#INIT COMPLETED
LEDPin.off()


# Central unit:
  . modules:
      - 1 i2c BME280 sensor
      - 1 i2c DS3231 hw clock
      - UART connection with the Raspberry
      
  . micropython dependencies: 
      - BME280.py
      - umqttsimple.py
      - ds3231_port
      
# Pheriferal sensors:
   . modules:
      - 1 i2c BME280 sensor
   . micropython dependencies: 
      - BME280.py
      - umqttsimple.py
      
# Raspberry:
   . software:
      - Raspbian lite 32bit with Xorg server but without desktop environment
      - Nodered
      - Influxdb
      - Mosquitto
      - autoexec bash script from /etc/rc.local
      - feh and python script to control it for screensaver
      
   . hardware
      - gpio buttons
      - hdmi display
      - optional usb drive to store influxdb data
      - UART connection with the main microcontroller


# gestisce i comandi ricevuti
def sub_callback(topic, msg):
    global thisRun, MQTT_REFRESH_DELAY
    topic = topic.decode('utf-8')
    msg = msg.decode('utf-8')
    tf_echo("MQTT", "new message: {}/{}".format(topic, msg))
    
    if topic == 'thermostat/get/outdoors':
        tf_echo("MQTT", "immediate measurement requested")
        thisRun += MQTT_REFRESH_DELAY
    
        
def connect_mqtt():
    global client_ID, mqtt_server, mqtt_port, mqtt_user, mqtt_pswd
    try:
        LEDPin.on()
        client = umqttsimple.MQTTClient(client_ID, mqtt_server, mqtt_port, mqtt_user, mqtt_pswd)
        client.set_callback(sub_callback) #cosa fare se ci sono nuovi messaggi? chiama sub_callback
        client.connect()
        tf_echo("MQTT", "Connected to {} MQTT broker".format(mqtt_server))
        return client
    except Exception as e:
        tf_echo("MQTT", "Connection failed ({})".format(e))
        return None
    finally:
        LEDPin.off()
        

def attempt_connection_or_restart():
    client = None
    for i in range(100): #proviamo a riconnetterci per 10 minuti, poi proviamo un riavvio
        client = connect_mqtt()
        if client:
            return client
        tf_echo("MQTT", "Trying to connect again.")
        time.sleep(MQTT_REFRESH_DELAY/10000) #ogni 6 sec
    machine.reset()


while True:
        
    if gc.mem_free() < 102000:
        gc.collect()
    
    if blindmode:
        blind_cycles_countdown-=1
        tf_echo("SYS", "Not sending any data while sensors are missing.")
        
    else:
        try:
            # pubblico le misurazioni
            measurements = {"temperature": bme.temperature, \
                             "humidity":   bme.humidity,  \
                             "pressure":   bme.pressure, \
                             "sensor":     "outdoor" }
            
            LEDPin.on()
            client = attempt_connection_or_restart()
            client.publish(TOPICS_PUB["readings"], json.dumps(measurements))
            tf_echo("MQTT", "publishing measurements")
            client.disconnect()
        
        except Exception as e:
            tf_echo("MQTT", "connection lost ({}).".format(e))
        
        finally:
            client = None
            LEDPin.off()

    if blindmode and blind_cycles_countdown <1:
        # reset
        tf_echo("SYS", "Rebooting now")
        machine.reset()
        
    time.sleep(LOOP_DELAY)

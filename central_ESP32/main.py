try:

    # impostazioni in formato json salvate su file
    with open('./cur_settings.json', 'r') as f:
        prev_settings = json.load(f)
    cur_settings = prev_settings.copy()

    if blindmode:
        OPMODE = "off"
        TARGET_T = PARAMETRI["inverno"]["minima"]
    else:
        #OPMODE: estate, inverno, off
        OPMODE = cur_settings["cur_mode"]
        TARGET_T = float(cur_settings["cur_target_temp"])


    def switch_this(machine, cmd):
        global blindmode
        activity = "OFF"
        
        if blindmode:
            tf_echo("THERM", "WARNING: missing sensors. Turning OFF {}".format(machine))
        else:
            if cmd == STATUS_LBL[MACCHINE[machine]["status"]]:
                tf_echo("THERM", "{}: è già {}".format(machine, cmd))
                # ma per sicurezza agisco lo stesso sul pin corrispondente
            else:
                MACCHINE[machine]["status"] = MACCHINE[machine]["pin"].value()
                tf_echo("THERM", "{}: {}".format(machine, cmd))
            
        if cmd == "ON" and machine == PARAMETRI[OPMODE]["macchina"] and not blindmode: # non accendo la caldaia d'estate.. 
            MACCHINE[machine]["pin"].on()
            activity = MACCHINE[machine]["act"]
        elif cmd == "OFF" or blindmode:
            MACCHINE[machine]["pin"].off()          
            
        return activity

        
        
    # gestisce i messaggi ricevuti
    def mqtt_callback(topic, msg):
        global TOPICS_SUB, OUTSIDE
        
        topic = topic.decode('utf-8')
        msg = msg.decode('utf-8')
        #publish_mqtt(MSG_ACK, tf_echo("MQTT", "ACK: {} = {}".format(topic, msg)))
        
        address = topic.split("/")
        
        if address[1] == "readings":
            try:
                tf_echo("MQTT", "Outside sensor: {}/{}".format(topic, msg))
                OUTSIDE = json.loads(msg)
                print(OUTSIDE)
                print(type(OUTSIDE))
            except Exception as e:
                tf_echo("MQTT", "ERRORE: {}".format(e))
        else:
            tf_echo("MQTT", "Messaggio ignorato.")
    
    
    def mqtt_connect():
        global client_ID, mqtt_server, mqtt_port, mqtt_user, mqtt_pswd
        try:
            LEDPin.on()
            client = umqttsimple.MQTTClient(client_ID, mqtt_server, mqtt_port, mqtt_user, mqtt_pswd)
            client.set_callback(mqtt_callback) #cosa fare se ci sono nuovi messaggi? chiama mqtt_callback
            client.connect()
            tf_echo("MQTT", "Connected to {} MQTT broker".format(mqtt_server))
            return client
        except Exception as e:
            tf_echo("MQTT", "Connection failed ({})".format(e))
            return None
        finally:
            LEDPin.off()


    # def publish_mqtt(topic, message):
        # global client
        # if client:
            # try:
                # LEDPin.on()
                # tf_echo("MQTT", "Publishing " + topic)
                # client.publish(topic, message)
            # except Exception as e:
                # print(e)
                # client.disconnect()
                # client = None
                # tf_echo("MQTT", "Connection lost")# ({}). Reconnecting in {}s".format(e, (MQTT_REFRESH_DELAY*60 - (thisRun - prevUARTrun))/1000))
            # finally:
                # LEDPin.off()
        # else:
            # tf_echo("MQTT", "Not connected")
            # pass
            

    # MAIN
    prevThermRun = 0
    prevUARTrun = 0
    prevMQTTrun = 0
    activity = "off"
    mqtt_client = False

    tf_echo("SYS","starting main execution cycle..")

    while True:
        syslog = []
        thermlog = []
        
        time.sleep(LOOP_DELAY/1000)
        thisRun = int(round(time.time() * 1000))
        #tf_echo("SYS", thisRun)
        
        
        if not mqtt_client:
            try:
                mqtt_client = mqtt_connect()
                for topic_name, topic_addr in TOPICS_SUB.items():
                    mqtt_client.subscribe(topic_addr)
                    tf_echo("MQTT", "Subscribing to {}".format(topic_addr))
            except Exception as e:
                tf_echo("MQTT", "Connection failed ({})".format(e))
                
        elif thisRun -prevMQTTrun >= MQTT_REFRESH_DELAY:
            prevMQTTrun = thisRun
            
            try:
                LEDPin.on()
                mqtt_client.check_msg()
            except Exception as e:
                tf_echo("MQTT", "ERROR: Failed to retrieve new message ({})".format(e))
            finally:
                LEDPin.off()

       
        if thisRun -prevUARTrun >= UART_REFRESH_DELAY:
            prevUARTrun = thisRun
            
            try:
                LEDPin.on()
                if uart.any():
                    tf_echo("UART", "receving instructions..")
                    
                    while uart.any():
                        bin_data = uart.readline()
                        tf_echo("UART",bin_data.decode('utf-8'))
                        
                        try:
                            cmd = json.loads(bin_data.decode('utf-8'))
                            if cmd["topic"]=="CMD":
                                if "target_t" in cmd["data"].keys():
                                    TARGET_T = float(cmd["data"]["target_t"])
                                    uart_send("ACK", tf_echo("UART", "ACK: target Temp is {}".format(TARGET_T)))
                                            
                                elif "opmode" in cmd["data"].keys() and not blindmode:
                                    OPMODE = cmd["data"]["opmode"]                      
                                    uart_send("ACK", tf_echo("UART", "ACK: operational mode is {}".format(OPMODE)))
                            else:
                                uart_send("ACK", tf_echo("UART", "ERROR: unknown command."))
                                
                        except Exception as e:
                            syslog.append(tf_echo("ERROR", "could not read incoming UART data. {}".format(e)))
                        
            
            except Exception as e:
                syslog.append(tf_echo("ERROR", "UART: {}".format(e)))
            
            finally:
                LEDPin.off()
                

        # THERMOSTAT
        if thisRun - prevThermRun >= THERM_REFRESH_DELAY:
            prevThermRun = thisRun
            
            if blindmode:
                blind_cycles_countdown-=1
            
            if gc.mem_free() < 102000:
                gc.collect()
            
            try:
                cur_t = bme.temperature
            except Exception as e:
                syslog.append(tf_echo("ERROR", "BME sensor malfuction ({})".format(e)))
                blindmode = True
                
                syslog.append(tf_echo("SYS", "Shutting down in {} cycles...".format(blind_cycles_countdown)))
                time.sleep(5)
                #machine.reset()
                #break

            
            # TARGET FAILSAFE
            if OPMODE != "off":
                for m in ["inverno", "estate"]:
                    if OPMODE == m:
                        if TARGET_T < PARAMETRI[m]["minima"]:
                            TARGET_T = PARAMETRI[m]["minima"]
                            thermlog.append(tf_echo("THERM", "Temperatura target troppo bassa. Reimpostata a {:.1f}°C".format(PARAMETRI[m]["minima"])))
                        elif TARGET_T > PARAMETRI[m]["massima"]:
                            TARGET_T = PARAMETRI[m]["massima"]
                            thermlog.append(tf_echo("THERM", "Temperatura target troppo alta. Reimpostata a {:.1f}°C".format(PARAMETRI[m]["massima"])))
                thermlog.append(tf_echo("THERM", "Temperatura target: {:.1f}°C [attuale: {:.1f}°C]".format(TARGET_T, cur_t)))
                
            
            # MODE FAILSAFE
            if OPMODE == "off" and not blindmode:
                if cur_t <= PARAMETRI["inverno"]["minima"]:
                    OPMODE = "inverno"
                    TARGET_T = PARAMETRI["inverno"]["minima"]
                    thermlog.append(tf_echo("THERM", "Rilevata temperatura troppo bassa. Attivo riscaldamento."))
                elif cur_t >= PARAMETRI["estate"]["massima"]:
                    OPMODE = "estate"
                    TARGET_T = PARAMETRI["estate"]["massima"]
                    thermlog.append(tf_echo("THERM", "Rilevata temperatura troppo alta. Attivo raffrescamento."))
            elif OPMODE == "inverno":
                if cur_t >= PARAMETRI[OPMODE]["massima"]:
                    OPMODE = "off"
                    thermlog.append(tf_echo("THERM", "Rilevata temperatura troppo alta. Spengo il riscaldamento."))
            elif OPMODE == "estate":
                # re-implementare?? # non ammetto una differenza superiore a 6°C con l'esterno
                #if (OUTSIDE["temperature"] != None and OUTSIDE["temperature"] - cur_t > PARAMETRI[OPMODE]["diff_max"]) or \
                if cur_t <= PARAMETRI[OPMODE]["minima"]:
                    OPMODE = "off"
                    thermlog.append(tf_echo("THERM", "Rilevata temperatura troppo bassa. Spengo il raffrescamento."))
            thermlog.append(tf_echo("THERM", "Modalità operativa: {}".format(OPMODE)))
                
            
            # ACTIVITY
            for m in PARAMETRI.keys(): # estate, inverno, off
                if OPMODE == "off" and m != "off":
                    activity = switch_this(PARAMETRI[m]["macchina"], "OFF")
                    
                elif OPMODE == m and m != "off":
                    w = PARAMETRI[m]["macchina"]
    #                 if cur_t > (TARGET_T - (PARAMETRI[m]["isteresi"]/2.0)) \
    #                    and cur_t < (TARGET_T + (PARAMETRI[m]["isteresi"]/2.0)): # sono dentro l'intervallo di isteresi
    #                     activity = switch_this(w, "OFF")
                        
                    if cur_t < (TARGET_T - (PARAMETRI[m]["isteresi"]/2.0)): # sono sotto il target
                        if m == "inverno":
                            activity = switch_this(w, "ON")
                            thermlog.append(tf_echo("THERM", "Temperatura target non ancora raggiunta..."))
                        elif m == "estate":
                            activity = switch_this(w, "OFF")
                            thermlog.append(tf_echo("THERM", "Rilevata temperatura inferiore al target. Spengo il raffrescamento."))
                        
                    elif cur_t > (TARGET_T + (PARAMETRI[m]["isteresi"]/2.0)): # sono sopra il target
                        if m == "inverno":
                            activity = switch_this(w, "OFF")
                            thermlog.append(tf_echo("THERM", "Rilevata temperatura superiore al target. Spengo il riscaldamento."))
                        elif m == "estate":
                            activity = switch_this(w, "ON")
                            thermlog.append(tf_echo("THERM", "Temperatura target non ancora raggiunta..."))
                                
                            
            cur_settings["cur_mode"] = OPMODE
            cur_settings["cur_target_temp"] = TARGET_T
            
            # salva solo se diversi!
            if not cur_settings == prev_settings:
                tf_echo("THERM", "Salvo le nuove impostazioni..")
                with open('./cur_settings.json', 'w') as f:
                    json.dump(cur_settings, f) #scrive su f
            prev_settings = cur_settings.copy()
            
            if not blindmode:
                measurements = {"sensor": "indoor", \
                                "temperature": bme.temperature, \
                                "humidity": bme.humidity,  \
                                "pressure": bme.pressure, \
                                "target_t": TARGET_T, \
                                "activity": activity }
            
                # send to RPI
                #if got_NTP or got_RTC:
                tf_echo("UART", "sending current cycle measurement data over")
                uart_send("MSR", measurements)
                time.sleep(1)
                
                tf_echo("UART", "sending current cycle thermostat log data over: {}".format(measurements))
                uart_send("THERM", thermlog)
                time.sleep(1)
    #             else:
    #                 syslog.append(tf_echo("WARNING","not sending data while time is not available."))
                
            
            if got_RTC:
                uart_send("TIME", ds3231.get_time()) #time.localtime())
            
            
            # comunico a RPI
            tf_echo("UART", "sending current cycle log data over")
            uart_send("LOG", syslog)
            
            
            if blindmode and blind_cycles_countdown <1:
                # halt
                tf_echo("SYS", "shutting down NOW")
                machine.deepsleep()
            
            # ogni tanto prendi l'ora esatta...
            if thisRun -prevUARTrun >= RTC_SYNC_DELAY and got_RTC:
                time.localtime(ds3231.get_time())
                
            # ogni tanto sincronizza NTP...
            if thisRun -prevUARTrun >= NTP_SYNC_DELAY:
                wlan_connect()
                try_NTP(got_RTC, RTC_TIMEZONE_OFFSET)
                
            
except Exception as e:
    pin_heat.off()
    pin_cool.off()
    print(e)
    raise e



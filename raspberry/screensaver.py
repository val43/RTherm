import os, sys, getopt, subprocess, socket
#import xprintidle
from time import sleep


pic_dir = "/home/pi/screensaver/img"
feh_proc = None

# GPIO.setmode(GPIO.BCM)
# pins = [31, 32, 36, 38]
# for i in pins:
    # GPIO.setup(i, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    # GPIO.add_event_detect(i, GPIO.FALLING)
 

# def check_pid(pid):
    # """ Check For the existence of a unix pid. """
    # if (pid==None):
        # return False
    # try:
    #    #sig 0 non fa nulla
        # os.kill(pid, 0)
        # return True
    # except OSError:
        # return False


def main(argv):
    global pic_dir, feh_proc
     
    envv = os.environ.copy()
    envv['DISPLAY'] = ':0'
    
    feh_pid = None
    
    # defaults (seconds)
    idlewait = 60*15
    slidetime = 60*5

    try:
        opts, args = getopt.getopt(argv, 's:i:', ['slidetime=', 'idlewait='])
        for opt,arg in opts:
            if opt in ("-s", "--slidetime"):
                slidetime = int(arg)
            elif opt in ("-i", "--idlewait"):
                idlewait = int(arg)
            else:
                raise Exception()

    except:
        print("istruzioni: screensaver.py --slidetime <secondi> --idlewait <secondi>")
        sys.exit(2)

    print("wait for {}s".format(idlewait))
    print("then change picture every {}s".format(slidetime))
    
    

    while True:
        
        # verifico idlewait di xserver su display :0
        xidle = subprocess.check_output(['xprintidle'], shell=True, env=envv).decode(encoding='UTF-8')
        xidle = int(int(xidle)/1000)
        print("timer: {}/{}".format(xidle, idlewait))

        # verifico anche che feh non sia già in esecuzione usando /proc/ fs
        if xidle >= idlewait and feh_pid is None:
            
            print("Inizio slideshow")

            try:
                feh_proc = subprocess.Popen(['feh', '-q', '-x', '-F', '-N', '-r', '-Y', '-Z', '-B black', '-D', str(slidetime), pic_dir], stdout=subprocess.PIPE, env=envv) #stderr=subprocess.PIPE, 
                feh_pid = feh_proc.pid
                print("nuovo PID di feh: {}".format(feh_pid))
                # -q quiet, doesn't report non fatal errors
                # -x borderless
                # -F fullscreen
                # -N no menus
                # -r recursive
                # -Y hide pointer
                # -Z auto zoom
                ## -z randomize
                # -B background color white/black/checks
                # -D slideshow delay
            except Exception as e:
                print("errore durante l'avvio di Feh: {}".format(e))
                continue
        
            try:
                conn, addr = sock.accept()
                sock.settimeout(0) # no timeout
                print("Attendo un comando da NodeRed")
                data = conn.recv(4) # 4 bytes
                conn.close()
                print("Comandi ricevuti: "+str(data))
                
                if data.decode("utf-8") == "kill":
                    try:
                        feh_proc.terminate()
                        feh_pid = None
                    except Exception as e:
                        print(e)
                else:
                    print("comando sconosciuto")
                        
            except Exception as e:
                print("errore del socket: {}".format(e))
                feh_proc.terminate()
                feh_pid = None
                sleep(1)
                
        
            # for i in pins:
                # GPIO.add_event_callback(i, callback=lambda procobj: killfeh(feh_proc), bouncetime=200)

        elif xidle < idlewait and feh_pid is not None:
            feh_proc.terminate()
            feh_pid = None
            print("feh terminato")
        
        else:
            sleep(10)


if __name__ == "__main__":
    try:
        socket.setdefaulttimeout(9)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            #sock.settimeout(0) # no timeout
            sock.bind(('127.0.0.1', 6969)) #localhost only, port 6969
            sock.listen(1) #only 1 client
            # sock.setblocking(True)
            # pollerObj = select.poll()
            # pollerObj.register(sock, select.POLLIN)

            main(sys.argv[1:])
            
    except (KeyboardInterrupt, EOFError) as err: 
        # non lasciare processi zombie
        if sock:
            print("closing socket..")
            sock.close()
        if feh_proc:
            print("terminating feh..")
            feh_proc.kill()
        print(err)
        print(err.args)
        sys.exit()

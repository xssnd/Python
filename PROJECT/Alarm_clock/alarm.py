# import required library
from tkinter import *
import datetime
import time
import winsound
from threading import *

# Create Object 
root = Tk()

# Set Geometry
root.geometry("400x200")

# Use Threading
def Threading():
    t1=Thread(target=alarm)
    t1.start()

def alarm():
    #infinite loop
    while True:
        # Set Alarm
        set_time = f"{hour.get()}:{minute.get()}:{second.get()}"

        # wait for one seconds
        time.sleep(1)

        # Get current time
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        print(current_time,set_time)

        #check wether set alarm is equal to current time or not
        if current_time == set_time:
            print("Time to Make Noise")
            # Playing sound
            winsound.PlaySound("sound.wav", winsound.SND_ASYNC)

    
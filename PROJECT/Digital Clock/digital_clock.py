import tkinter as tk
import time

def update_clock():
    current_date = time.strftime('%A, %d-%m-%Y')
    current_time = time.strftime('%H:%M:%S') # format hours:minute:second:millisecond
    clock_label.config(text=f"{current_date} \n {current_time}")
    root.after(1, update_clock)

root = tk.Tk()
root.title("Digital Clock")

clock_label = tk.Label(root,font=('calibri', 50, 'bold'), background='black', foreground='yellow')
clock_label.pack(anchor='center')

update_clock()

root.mainloop()
import tkinter as tk
import time 
import math

def update_analog_clock():
    current_time = time.localtime()
    hour = current_time.tm_hour
    minute = current_time.tm_min
    second = current_time.tm_sec

    # update analog clock
    hour_angle = math.radians(30 * (hour % 12) + 0.5 * minute)
    minute_angle = math.radians(6 * minute + 0.1 * second)
    second_angle = math.radians(6 * second)

    hour_length = 50
    minute_length = 80
    second_length = 90

    hour_x = center_x + hour_length * math.sin(hour_angle)
    hour_y = center_y - hour_length * math.cos(hour_angle)
    minute_x = center_x + minute_length * math.sin(minute_angle)
    minute_y = center_y - minute_length * math.cos(minute_angle)
    second_x = center_x + second_length * math.sin(second_angle)
    second_y = center_y - second_length * math.cos(second_angle)

    canvas.coords(hour_hand, center_x, center_y, hour_x, hour_y)
    canvas.coords(minute_hand, center_x, center_y, minute_x, minute_y)
    canvas.coords(second_hand, center_x, center_y, second_x, second_y)

    #update digital clock
    current_date = time.strftime('%A, %d-%m-%Y')
    current_time_str = time.strftime("%H:%M:%S")
    digital_clock.config(text = f"{current_date} \n {current_time_str}" )

    # Schedule the next update
    root.after( 1000, update_analog_clock)

# Create tkinter window
root = tk.Tk()
root.title("Analog and Digital Clock")

# Create canvas for analog clock
canvas = tk.Canvas(root, width=300, height=300, bg='white')
canvas.pack()

# Draw clock face
center_x = 150
center_y = 150
canvas.create_oval(center_x - 90, center_y - 90, center_x + 90, center_y + 90, width=2)

# Add Number to clock 1 - 12
numbers = [(center_x + 80 * math.sin(math.radians(angle)), center_y - 80 * math.cos(math.radians(angle))) for angle in range(0, 360, 30)]
for i, number in enumerate([12,1,2,3,4,5,6,7,8,9,10,11]):
    canvas.create_text(numbers[i][0], numbers[i][1], text=str(number))

# Create Clock hands 
hour_hand = canvas.create_line(0,0,0,0, width = 4, fill='blue')
minute_hand = canvas.create_line(0,0,0,0, width=3, fill='green')
second_hand = canvas.create_line(0,0,0,0, width=1, fill='red')

# create digital clock
digital_clock = tk.Label(root, text="", font=('calibri', 30, 'bold'), bg="white")
digital_clock.pack()

# start clock update
update_analog_clock()

# tkinter event loop
root.mainloop()

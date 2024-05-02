import tkinter as tk

# Function to evaluate the expression
def calculate():
    try:
        result.set(eval(entry.get()))  # Evaluate the expression and set the result
    except:
        result.set("Error")  # If there's an error in the expression, set result to "Error"

# Create a Tkinter window
root = tk.Tk()
root.title("Calculator")

# Variable to store the result
result = tk.StringVar()

# Entry widget to display and input the expression
entry = tk.Entry(root, textvariable=result, font=('Arial', 14), bd=5, insertwidth=4, width=14)
entry.grid(row=0, column=0, columnspan=4)

# Buttons for numbers and operators
buttons = [
    ('7', 1, 0), ('8', 1, 1), ('9', 1, 2), ('/', 1, 3),
    ('4', 2, 0), ('5', 2, 1), ('6', 2, 2), ('*', 2, 3),
    ('1', 3, 0), ('2', 3, 1), ('3', 3, 2), ('-', 3, 3),
    ('0', 4, 0), ('.', 4, 1), ('=', 4, 2), ('+', 4, 3)
]

# Create and place the buttons
for (text, row, col) in buttons:
    button = tk.Button(root, text=text, font=('Arial', 14), padx=10, pady=10,
                       command=lambda t=text: entry.insert(tk.END, t))
    button.grid(row=row, column=col, sticky='news')

# Bind the Enter key to calculate function
root.bind('<Return>', lambda event=None: calculate())

# Run the Tkinter event loop
root.mainloop()
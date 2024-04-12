"""
• Don't do this!
• Make sure there is a proper end-condition. (exit-condition)
• Use Ctrl-C to stop it

"""
import random

total = 0
while total >= 0:
    print(total)
    total += random.randrange(25)
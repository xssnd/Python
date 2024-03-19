import random

hidden = random.randrange(1,20)
user_input = input("Enter your guess: ")
print(user_input)
guess = int(user_input)
if guess == hidden:
    print("HIT")
elif guess < hidden:
    print("Your number too low")
else:
    print("your number too high")

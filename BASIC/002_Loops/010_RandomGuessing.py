import random

hidden = random.randrange(1, 50)
debug = False
while True:
    if debug:
        print("Debug: " , hidden)

    user_input = input("Enter your guess : ")
    print(user_input)
    
    # option x and exit game
    if user_input == 'x':
        print("Exiting... ")
        exit()
    
    #option s to showing hidden number
    if user_input == 's':
        print("Hidden number is ", hidden)
        continue

    # option d for debug
    if user_input == 'd':
        print("debugging :" , hidden)
        continue
    
    guess = int(user_input)
    if guess == hidden:
        print("HIT")
        break

    if guess < hidden:
        print("Your guess is too low")
    else:
        print("Your guess too high")

import random

number = 0

while number <= 10000:
    print(number)
    number += random.randrange(20)
    if number % 17 == 1:
        break
    if number ** 2 % 13 == 7:
        break

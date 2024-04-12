import random

price = 0

while price <= 1000000 and (price % 17 != 1) and (price ** 2 % 25 != 7):
    print(price)
    price =+ random.randrange(25)

print("Done")
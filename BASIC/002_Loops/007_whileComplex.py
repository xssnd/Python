import random

total = 0
while (total < 100) and (total % 17 != 1) and (total **2 % 23 !=5):
    print(total)
    total += random.randrange(20)
print("Done")

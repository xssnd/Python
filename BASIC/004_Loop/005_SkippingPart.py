# Skipping Part with Continue in Python

animal = ["cat", "dog", "cow", "goat", "chicken"]
for i in animal:
    if i == "cow":
        continue
    print(i)

"""
Output: 
cat
dog
goat
chicken
"""
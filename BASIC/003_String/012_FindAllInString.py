txt = "Orange Cat with White Dogs"
print(txt)
a = input(str("Find any substring in text : "))
if a in txt:
    print("Found it")
else:
    print("There's no", a, "in :", txt)
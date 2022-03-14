txt = "hello snake"
for x in txt:
    if x == ' ':
        continue
    if x == 'n':
        break
    print(x)
print("done")

animal = ["cat", "dog", "cow", "goat", "chicken", "ant","pamda","bear"]
for i in animal:
    if i == "cow":
        continue
    if i == "goat":
        break
    print(i)
print("done")

"""
Output
cat
dog
done

"""
text = "The orange cat climbed the green tree."

print(text.find("nge"))     # 7
print(text.find("the"))     # 23
print(text.find("dog"))     # -1

print(text.find("c"))       # 11
print(text.find("c", 8))    # 11

print(text.rfind("c", 8))   # 15

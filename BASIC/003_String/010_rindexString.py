text = "The orange cat climbed the green tree."
print(text.rindex("c"))     #14
print(text.rindex("c", 8))  # 14
print(text.rindex("c", 8, 13))  #13

print(text.rindex("gr", 8)) # 26
print(text.rindex("gr", 8, 16)) #Error substring not found

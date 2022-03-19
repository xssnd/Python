# Index String Range

text = "The orange cat climbed the green tree."
print(text.index("c"))      # 11
print(text.index("c", 9))   # 11
print(text.index("gr", 8))  # 27
print(text.index("gr", 8, 12)) # Error



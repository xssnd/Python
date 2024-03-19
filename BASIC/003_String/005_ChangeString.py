# Strings in Python are immutable - they never change.

text = "abcde"
print(text)     #abcde

text = text[:2] + 'Z' + text[3:]
print(text)     #abZde

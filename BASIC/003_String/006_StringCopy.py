text = "abcde"
print(text)     #abcde

text = text + "yz"
print(text)     # abcdeyz

other = text    
print(other)    # abcdeyz
text = "xyz"    

print(text)     # xyz
print(other)    # abcdeyz

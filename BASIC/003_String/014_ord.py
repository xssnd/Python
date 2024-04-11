"""
Given a string representing one Unicode character, return an integer representing the Unicode code point of that character.
For example, ord('a') returns the integer 97 and ord('€') (Euro sign) returns 8364. This is the inverse of chr().
https://docs.python.org/3/library/functions.html#ord
"""
print( ord('a') ) # 97
print( ord('=') ) # 61
print( ord('\r') ) # 13
print( ord('\n') ) # 10
print( ord(' ') ) # 32

print( ord('á') ) # 225
print( ord('ó') ) # 243
print( ord('') ) # 148
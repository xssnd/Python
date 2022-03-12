# Comparison Operators
#   ==      equal
#   !=      not equal
#   <       less than
#   <=      less than or equal
#   >       Greater than
#   >=      Greater than or equal

a = "50"
b = 50
print(a == b)       # False
print(a != b)       # True
print(b == 50.0)    # True

print(None == None) # True
print(None == False) # False

# DO NOT compare different Types

x = 20
y = 5
print(x > y)    # True

x = "20"
y = "5"
print(x > y)    # False

x = "20"
y = 5
print(x > y)    # True

x = 20
y = "5"
print(x > y)    # False

# OPERATOR and or not
if COND:
    do something
else:
    do something other
  
if not COND:
    do something other
  
if COND1 and COND2:
    do something
 
if COND1 or COND2:
    do something
 
if COND1 and not COND2:
    do something



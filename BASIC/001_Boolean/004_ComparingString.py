inp1 = input("please type a string: ")
inp2 = input("Please type another string: ")
print("-" * 30)
print(inp1, " vs ", inp2)
print("How to compare?")
print("1. ASCII")
print("2. Length")
print("-" * 30)
method = input()

if method == '1':
    first = inp1 > inp2
    second = inp1 < inp2
elif method == '2':
    first = len(inp1) > len(inp2)
    second = len(inp1) < len(inp2)

if first:
    print("First is bigger: ")
elif second:
    print("First is smaller: ")
else:
    print("They are equal")

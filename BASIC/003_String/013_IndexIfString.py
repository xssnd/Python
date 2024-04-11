txt = "The Black cat climbed the green tree"
print(txt)
sub = str(input("Any Char to Locate index in text : "))

if sub in txt:
    loc = txt.index(sub)
    print(sub+ " is at " + str(loc))
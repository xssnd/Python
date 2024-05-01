import argparse
import hashlib

# Parsing 
parser = argparse.ArgumentParser(prog="Hashing Password",description="Python Code to Hashing Password")
parser.add_argument("password", help="input password you want to hash")
parser.add_argument("-t", "--type",default="sha256",choices=['sha256','sha512','md5'])
args = parser.parse_args()

# Give Password to Hash
password = args.password
hashtype = args.type
m=getattr(hashlib,hashtype)()
m.update(password.encode())

# Output
print("< hash - type: " + hashtype + " > ")
print(m.hexdigest())
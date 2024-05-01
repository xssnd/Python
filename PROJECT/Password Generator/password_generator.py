import random
import string

def generate_password(length):
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for _ in range(length))
    return password

def main():
    try:
        length = int(input("Enter lenght of the password : "))
        if length <= 0:
            print("Please enter a positive integer more than zero")
            return
        password = generate_password(length)
        print("Generated Password : ", password)
    except:
        print("Invalid input. Please enter a valid integer")

if __name__ == "__main__":
    main()
import random
import string
def generate_secure_password(length):
    if length < 4:
        raise ValueError("La longitud mínima de la contraseña es 4.")
    characters = string.ascii_letters + string.digits + string.punctuation
    password = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
        random.choice(string.punctuation)
    ]
    password += random.choices(characters, k=length - 4)
    random.shuffle(password)
    return ''.join(password)
def run(params):
    length = params.get('length', 12)
    return generate_secure_password(length)
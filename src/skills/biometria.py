def biometric_auth(data):
    if 'fingerprint' in data:
        return "Autenticación exitosa mediante huella dactilar."
    elif 'voiceprint' in data:
        return "Autenticación exitosa mediante reconocimiento de voz."
    elif 'iris_scan' in data:
        return "Autenticación exitosa mediante escaneo de iris."
    else:
        return "Fallo en la autenticación: método biométrico no reconocido."
def run(auth_data):
    return biometric_auth(auth_data)
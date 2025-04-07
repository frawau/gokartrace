import json
from cryptography.fernet import Fernet
from base64 import b64encode, b64decode


def dataencode(cround, data):
    docrypt = Fernet(cround.qr_fernet)
    return b64encode(docrypt.encrypt(str(data).encode())).decode("ascii")


def datadecode(cround, data):
    docrypt = Fernet(cround.qr_fernet)
    return int(docrtpt.decrypt(b64decode(data.encode())))

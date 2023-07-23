import pyAesCrypt
import os

from dotenv import load_dotenv


SERVICE_FILE = "service_account.json"
SERVICE_FILE_AES = SERVICE_FILE + ".aes"
# get abspath


def get_service_account_file_path():
    if os.path.exists(SERVICE_FILE):
        return SERVICE_FILE
    else:
        load_dotenv()
        password = os.getenv("AES_PASSWORD")
        if not password:
            raise ValueError("AES_PASSWORD not set in env")
        # decrypt the encrypted file
        pyAesCrypt.decryptFile(SERVICE_FILE_AES, SERVICE_FILE, password)
        return SERVICE_FILE

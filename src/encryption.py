import pyAesCrypt
import os

from dotenv import load_dotenv


SERVICE_FILE_PATH = "service_account.json"
SERVICE_FILE_AES_PATH = SERVICE_FILE_PATH + ".aes"
# get abspath


def get_service_account_file_path():
    if os.path.exists(SERVICE_FILE_PATH):
        return SERVICE_FILE_PATH
    else:
        load_dotenv()
        password = os.getenv("AES_PASSWORD")
        if not password:
            raise ValueError("AES_PASSWORD not set in env")
        # decrypt the encrypted file
        pyAesCrypt.decryptFile(SERVICE_FILE_AES_PATH, SERVICE_FILE_PATH, password)
        return SERVICE_FILE_PATH

if __name__ == "__main__":
    print(get_service_account_file_path())

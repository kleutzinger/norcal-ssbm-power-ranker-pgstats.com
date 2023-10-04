"""
todo:
- [x] import redis url from env
"""
import os
from dotenv import load_dotenv

load_dotenv()

import json
import gzip
from io import BytesIO
from typing import Optional
import redis
import fakeredis

REDIS_URL = os.getenv("REDIS_URL")
if REDIS_URL is None:
    # use fakeredis
    r = fakeredis.FakeRedis()
else:
    r = redis.Redis.from_url(REDIS_URL, db=0)


def decompressBytesToString(inputBytes):
    """
    decompress the given byte array (which must be valid
    compressed gzip data) and return the decoded text (utf-8).
    """
    bio = BytesIO()
    stream = BytesIO(inputBytes)
    decompressor = gzip.GzipFile(fileobj=stream, mode="r")
    while True:  # until EOF
        chunk = decompressor.read(8192)
        if not chunk:
            decompressor.close()
            bio.seek(0)
            return bio.read().decode("utf-8")
        bio.write(chunk)


def compressStringToBytes(inputString):
    """
    read the given string, encode it in utf-8,
    compress the data and return it as a byte array.
    """
    bio = BytesIO()
    bio.write(inputString.encode("utf-8"))
    bio.seek(0)
    stream = BytesIO()
    compressor = gzip.GzipFile(fileobj=stream, mode="w")
    while True:  # until EOF
        chunk = bio.read(8192)
        if not chunk:  # EOF?
            compressor.close()
            return stream.getvalue()
        compressor.write(chunk)


def setj(key: str, value: dict) -> Optional[bool]:
    """a wrapper around redis set that converts the value to compressed json"""
    return r.set(key, compressStringToBytes(json.dumps(value)))


def getj(key: str) -> Optional[dict]:
    """a wrapper around redis get that converts the value from json"""
    val = r.get(key)
    if val is None:
        return None
    return json.loads(decompressBytesToString(val))


def main():
    # r.set('foo', 'bar')
    d = dict(a=1, b=2)
    r.set("foo", json.dumps(d))
    print(json.loads(r.get("foo")))
    setj("foo", d)
    print(getj("foo"))
    # create_db_and_tables()
    # create_players()


if __name__ == "__main__":
    main()

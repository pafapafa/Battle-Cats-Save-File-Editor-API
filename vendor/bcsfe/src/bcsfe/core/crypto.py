from __future__ import annotations
import enum
import hashlib
import hmac
import random
from bcsfe import core


class HashAlgorithm(enum.Enum):


    MD5 = enum.auto()
    SHA1 = enum.auto()
    SHA256 = enum.auto()


class Hash:


    def __init__(self, algorithm: HashAlgorithm):


        self.algorithm = algorithm

    def get_hash(
        self,
        data: core.Data,
        length: int | None = None,
    ) -> core.Data:


        if self.algorithm == HashAlgorithm.MD5:
            hash = hashlib.md5()
        elif self.algorithm == HashAlgorithm.SHA1:
            hash = hashlib.sha1()
        elif self.algorithm == HashAlgorithm.SHA256:
            hash = hashlib.sha256()
        else:
            raise ValueError("Invalid hash algorithm")
        hash.update(data.get_bytes())
        if length is None:
            return core.Data(hash.digest())
        return core.Data(hash.digest()[:length])


class Random:


    @staticmethod
    def get_bytes(length: int) -> bytes:


        return bytes(random.getrandbits(8) for _ in range(length))

    @staticmethod
    def get_alpha_string(length: int) -> str:


        characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return "".join(random.choice(characters) for _ in range(length))

    @staticmethod
    def get_hex_string(length: int) -> str:


        characters = "0123456789abcdef"
        return "".join(random.choice(characters) for _ in range(length))

    @staticmethod
    def get_digits_string(length: int) -> str:


        characters = "0123456789"
        return "".join(random.choice(characters) for _ in range(length))


class Hmac:
    def __init__(self, algorithm: HashAlgorithm):
        self.algorithm = algorithm

    def get_hmac(self, key: core.Data, data: core.Data) -> core.Data:
        if self.algorithm == HashAlgorithm.MD5:
            alg = hashlib.md5
        elif self.algorithm == HashAlgorithm.SHA1:
            alg = hashlib.sha1
        elif self.algorithm == HashAlgorithm.SHA256:
            alg = hashlib.sha256
        else:
            raise ValueError("Invalid hash algorithm")
        hmac_data = hmac.new(
            key.get_bytes(), data.get_bytes(), digestmod=alg
        ).digest()
        return core.Data(hmac_data)


class NyankoSignature:
    def __init__(self, inquiry_code: str, data: str):
        self.inquiry_code = inquiry_code
        self.data = data

    def generate_signature(self) -> str:


        random_data = Random.get_hex_string(64)
        key = self.inquiry_code + random_data
        hmac_ = Hmac(HashAlgorithm.SHA256)
        signature = hmac_.get_hmac(core.Data(key), core.Data(self.data))

        return random_data + signature.to_hex()

    def generate_signature_v1(self) -> str:


        data = self.data + self.data
        random_data = Random.get_hex_string(40)
        key = self.inquiry_code + random_data
        hmac_ = Hmac(HashAlgorithm.SHA1)
        signature = hmac_.get_hmac(core.Data(key), core.Data(data))

        return random_data + signature.to_hex()

import json
import hashlib
import os
import argparse
import qrcode
import base64

from io import BytesIO
from uuid import uuid4
from ecdsa import SECP256k1, SigningKey
from ecdsa.util import randrange_from_seed__trytryagain
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2
from bitcoin.wallet import CBitcoinSecret
from bitcoin.signmessage import BitcoinMessage, VerifyMessage, SignMessage
from crypt import Crypt


class TU(object):  # Transaction Utilities
    private_key = None

    @classmethod
    def hash(cls, message):
        return hashlib.sha256(message).digest().encode('hex')

    @classmethod
    def get_bulletin_secret(cls):
        cipher = Crypt(cls.private_key)
        return hashlib.sha256(cipher.encrypt_consistent(cls.private_key)).digest().encode('hex')

    @classmethod
    def generate_deterministic_signature(cls):
        key = CBitcoinSecret(cls.private_key)
        signature = SignMessage(key, BitcoinMessage(cls.private_key, magic=''))
        return hashlib.sha256(signature.encode('hex')).digest().encode('hex')

    @classmethod
    def generate_signature(cls, message):
        key = CBitcoinSecret(cls.private_key)
        signature = SignMessage(key, BitcoinMessage(message, magic=''))
        return signature

    @classmethod
    def save(cls, items):
        if not isinstance(items, list):
            items = [items.to_dict(), ]
        else:
            items = [item.to_dict() for item in items]

        with open('miner_transactions.json', 'a+') as f:
            try:
                existing = json.loads(f.read())
            except:
                existing = []
            existing.extend(items)
            f.seek(0)
            f.truncate()
            f.write(json.dumps(existing, indent=4))
            f.truncate()
import json
import hashlib
import os
import base64
import time
import random
import sys

from io import BytesIO
from uuid import uuid4
from ecdsa import SECP256k1, SigningKey
from ecdsa.util import randrange_from_seed__trytryagain
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2
from bitcoin.wallet import CBitcoinSecret
from bitcoin.signmessage import BitcoinMessage, VerifyMessage, SignMessage
from crypt import Crypt
from coincurve.keys import PrivateKey
from coincurve._libsecp256k1 import ffi
from eccsnacks.curve25519 import scalarmult, scalarmult_base
from config import Config
from mongo import Mongo


class TU(object):  # Transaction Utilities

    @classmethod
    def hash(cls, message):
        return hashlib.sha256(message).digest().encode('hex')

    @classmethod
    def generate_deterministic_signature(cls, config, message, private_key=None):
        if not private_key:
            private_key = config.private_key
        key = PrivateKey.from_hex(private_key)
        signature = key.sign(message)
        return base64.b64encode(signature)

    @classmethod
    def generate_signature_with_private_key(cls, private_key, message):
        x = ffi.new('long *')
        x[0] = random.SystemRandom().randint(0, sys.maxint)
        key = PrivateKey.from_hex(private_key)
        signature = key.sign(message, custom_nonce=(ffi.NULL, x))
        return base64.b64encode(signature)

    @classmethod
    def generate_signature(cls, message, private_key):
        x = ffi.new('long *')
        x[0] = random.SystemRandom().randint(0, sys.maxint)
        key = PrivateKey.from_hex(private_key)
        signature = key.sign(message, custom_nonce=(ffi.NULL, x))
        return base64.b64encode(signature)

    @classmethod
    def generate_rid(cls, config, bulletin_secret):
        if config.bulletin_secret == bulletin_secret:
            raise BaseException('bulletin secrets are identical. do you love yourself so much that you want a relationship on the blockchain?')
        bulletin_secrets = sorted([str(config.bulletin_secret), str(bulletin_secret)], key=str.lower)
        return hashlib.sha256(str(bulletin_secrets[0]) + str(bulletin_secrets[1])).digest().encode('hex')

    @classmethod
    def get_shared_secrets_by_rid(cls, config, mongo, rid):
        from blockchainutils import BU
        shared_secrets = []
        dh_public_keys = []
        dh_private_keys = []
        txns = BU.get_transactions_by_rid(config, mongo, rid, config.bulletin_secret, rid=True)
        for txn in txns:
            if str(txn['public_key']) == str(config.public_key) and txn['relationship']['dh_private_key']:
                dh_private_keys.append(txn['relationship']['dh_private_key'])
        txns = BU.get_transactions_by_rid(config, mongo, rid, config.bulletin_secret, rid=True, raw=True)
        for txn in txns:
            if str(txn['public_key']) != str(config.public_key) and txn['dh_public_key']:
                dh_public_keys.append(txn['dh_public_key'])
        for dh_public_key in dh_public_keys:
            for dh_private_key in dh_private_keys:
                shared_secrets.append(scalarmult(dh_private_key.decode('hex'), dh_public_key.decode('hex')))
        return shared_secrets

    @classmethod
    def save(cls, config, mongo, items):
        if not isinstance(items, list):
            items = [items.to_dict(), ]
        else:
            items = [item.to_dict() for item in items]

        for item in items:
            mongo.db.miner_transactions.insert(item)
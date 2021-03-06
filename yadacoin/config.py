import hashlib
import os
import json
import binascii
import base58
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import PrivateKey, PublicKey
from mnemonic import Mnemonic
from bip32utils import BIP32Key


class Config(object):
    def __init__(self, config):
        self.seed = config.get('seed', '')
        self.xprv = config.get('xprv', '')
        self.username = config.get('username', '')
        self.network = config.get('network', '')
        self.public_key = config['public_key']
        self.address = str(P2PKHBitcoinAddress.from_pubkey(self.public_key.decode('hex')))

        self.private_key = config['private_key']
        self.wif = self.to_wif(self.private_key)
        self.bulletin_secret = self.get_bulletin_secret()

        self.mongodb_host = config['mongodb_host']
        self.database = config['database']
        self.site_database = config['site_database']
        self.web_server_host = config['web_server_host']
        self.web_server_port = config['web_server_port']
        if config['peer_host'] == '0.0.0.0' or config['peer_host'] == 'localhost':
            raise Exception("cannot use localhost or 0.0.0.0, must specify public ipv4 address")
        if config['peer_host'] == '[my public ip]':
            raise Exception("please configure your peer_post to your public ipv4 address")
        self.peer_host = config['peer_host']
        self.peer_port = config['peer_port']
        self.serve_host = config['serve_host']
        self.serve_port = config['serve_port']
        self.callbackurl = config['callbackurl']
        self.fcm_key = config['fcm_key']

    @classmethod
    def generate(cls, xprv=None, prv=None, seed=None, child=None, username=None):
        # generate 12 word mnemonic seed
        if not seed and not xprv and not prv:
            mnemonic = Mnemonic('english')
            seed = mnemonic.generate(256)
        
        private_key = None
        if seed:
            # create bitcoin wallet
            entropy = mnemonic.to_entropy(seed)
            key = BIP32Key.fromEntropy(entropy)
            private_key = key.PrivateKey().encode('hex')
            extended_key = key.ExtendedKey()

        if prv:
            private_key = PrivateKey.from_hex(prv.decode('hex')).to_hex()
            extended_key = ''

        if xprv:
            key = BIP32Key.fromExtendedKey(xprv)
            private_key = key.PrivateKey().encode('hex')
            extended_key = key.ExtendedKey()
        
        if xprv and child:
            for x in child:
                key = key.ChildKey(int(x))
                private_key = key.PrivateKey().encode('hex')

        if not private_key:
            raise Exception('No key')

        return cls({
            "seed": seed or '',
            "xprv": extended_key or '',
            "private_key": private_key,
            "wif": cls.generate_wif(private_key),
            "public_key": PublicKey.from_point(key.K.pubkey.point.x(), key.K.pubkey.point.y()).format().encode('hex'),
            "address": str(key.Address()),
            "serve_host": "0.0.0.0",
            "serve_port": 8000,
            "peer_host": "",
            "peer_port": 8000,
            "web_server_host": "0.0.0.0",
            "web_server_port": 5000,
            "peer": "http://localhost:8000",
            "callbackurl": "http://0.0.0.0:5000/create-relationship",
            "fcm_key": "",
            "database": "yadacoin",
            "site_database": "yadacoinsite",
            "mongodb_host": "localhost",
            "mixpanel": "",
            "username": username or '',
            "network": "mainnet"
        })

    @classmethod
    def from_dict(cls, config):
        from transactionutils import TU
        cls.seed = config.get('seed', '')
        cls.xprv = config.get('xprv', '')
        cls.username = config.get('username', '')
        cls.network = config.get('network', '')
        cls.public_key = config['public_key']
        cls.address = str(P2PKHBitcoinAddress.from_pubkey(cls.public_key.decode('hex')))

        cls.private_key = config['private_key']
        cls.wif = cls.generate_wif(cls.private_key)
        cls.bulletin_secret = TU.generate_deterministic_signature(config, config['username'], config['private_key'])

        cls.mongodb_host = config['mongodb_host']
        cls.database = config['database']
        cls.site_database = config['site_database']
        cls.web_server_host = config['web_server_host']
        cls.web_server_port = config['web_server_port']
        if config['peer_host'] == '0.0.0.0' or config['peer_host'] == 'localhost':
            raise Exception("cannot use localhost or 0.0.0.0, must specify public ipv4 address")
        if config['peer_host'] == '[my public ip]':
            raise Exception("please configure your peer_post to your public ipv4 address")
        cls.peer_host = config['peer_host']
        cls.peer_port = config['peer_port']
        cls.serve_host = config['serve_host']
        cls.serve_port = config['serve_port']
        cls.callbackurl = config['callbackurl']
        cls.fcm_key = config['fcm_key']

    def get_bulletin_secret(self):
        from transactionutils import TU
        return TU.generate_deterministic_signature(self, self.username, self.private_key)

    def to_wif(self, private_key):
        private_key_static = private_key
        extended_key = "80"+private_key_static+"01"
        first_sha256 = hashlib.sha256(binascii.unhexlify(extended_key)).hexdigest()
        second_sha256 = hashlib.sha256(binascii.unhexlify(first_sha256)).hexdigest()
        final_key = extended_key+second_sha256[:8]
        wif = base58.b58encode(binascii.unhexlify(final_key))
        return wif

    @classmethod
    def generate_wif(cls, private_key):
        private_key_static = private_key
        extended_key = "80"+private_key_static+"01"
        first_sha256 = hashlib.sha256(binascii.unhexlify(extended_key)).hexdigest()
        second_sha256 = hashlib.sha256(binascii.unhexlify(first_sha256)).hexdigest()
        final_key = extended_key+second_sha256[:8]
        wif = base58.b58encode(binascii.unhexlify(final_key))
        return wif

    def to_dict(self):
        return {
            'seed': self.seed,
            'xprv': self.xprv,
            'public_key': self.public_key,
            'address': self.address,
            'private_key': self.private_key,
            'wif': self.wif,
            'bulletin_secret': self.bulletin_secret,
            'mongodb_host': self.mongodb_host,
            'username': self.username,
            'network': self.network,
            'database': self.database,
            'site_database': self.site_database,
            'web_server_host': self.web_server_host,
            'web_server_port': self.web_server_port,
            'peer_host': self.peer_host,
            'peer_port': self.peer_port,
            'serve_host': self.serve_host,
            'serve_port': self.serve_port,
            'fcm_key': self.fcm_key,
            'callbackurl': self.callbackurl
        }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)

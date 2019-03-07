import socketio
import socket
import json
import time
import signal
import sys
import requests
import base64
import humanhash
import re
import pymongo
import subprocess
import os
import multiprocessing
from sys import exit
from multiprocessing import Process, Value, Array, Pool
from socketIO_client import SocketIO, BaseNamespace
from flask import Flask, render_template, request, Response
from flask_cors import CORS
from yadacoin import (
    TransactionFactory, Transaction, MissingInputTransactionException,
    Input, Output, Block, Config, Peers, 
    Blockchain, BlockChainException, TU, BU, 
    Mongo, BlockFactory, NotEnoughMoneyException, Peer, 
    Consensus, PoolPayer, Faucet, Send, Graph, Serve, endpoints
)
from yadacoin import MiningPool
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from gevent import pywsgi, pool


def signal_handler(signal, frame):
        print('Closing... Or use ctrl + \\')
        sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

if __name__ == '__main__':
    multiprocessing.freeze_support()
    import argparse
    import os.path
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', nargs=None, help='serve, mine, or consensus')
    parser.add_argument('config', default="config.json", nargs="?", help='config file')
    parser.add_argument('to', default="", nargs="?", help='to')
    parser.add_argument('value', default=0, nargs="?", help='amount')
    parser.add_argument('-n', '--network', default='mainnet', help='Specify mainnet, testnet or regnet')
    parser.add_argument('-c', '--cores', default=multiprocessing.cpu_count(), help='Specify number of cores to use')
    parser.add_argument('-p', '--pool', default='', help='Specify pool to use')
    parser.add_argument('-d', '--debug', default=False, help='Debug messages')
    parser.add_argument('-r', '--reset', default=False, help='If blockchain is invalid, truncate at error block')
    args = parser.parse_args()

    if os.path.isfile(args.config):
        with open(args.config) as f:
            config = Config(json.loads(f.read()))
    else:
        print 'no config file found at \'%s\'' % args.config
        exit()

    mongo = Mongo(config)
    if args.mode == 'consensus':
        consensus = Consensus(config, mongo, args.debug)
        consensus.verify_existing_blockchain(reset=args.reset)
        while 1:
            wait = consensus.sync_bottom_up()
            if wait:
                time.sleep(1)

    elif args.mode == 'sendraw':
        from bip32utils import BIP32Key
        import pprint
        def subkey(index):
            qtctl_env = os.environ.copy()
            qtctl_env["QTCTL_KEY"] = "xprv9v3URixxtyRbDyys2zmY7xxtt2NvjpsdR3DHu7djw9AckBowqBFuSDamhVpn127WDfcbsGbSwqLayFueXEPrpyPTqMNbJ6XCnS7obNyDsyn"
            qtctl_env["QTCTL_ADDRESSVERSION"] = "0"
            key_raw = subprocess.check_output(
                "qtctl subkey-gen-int {}".format(index),
                env=qtctl_env, shell=True).decode('utf8')
            key = json.loads(key_raw)

            ex_key = BIP32Key.fromExtendedKey(key['xpriv'])
            private_key = ex_key.PrivateKey().encode('hex')

            return {'pubkey': key['base58_pub'], 'index': index, "private": private_key}

        keys = [subkey(i) for i in range(5)]
        print("generated a keyring of 5 addresses")
        pprint.pprint(keys)

        # Assemble the list of inputs
        inputs = []
        for key in keys:
            input_txns = BU.get_wallet_unspent_transactions(config, mongo, key['pubkey'])
            for tx in input_txns:
                for i, out in enumerate(tx['outputs']):
                    if out['to'] != key['pubkey']:
                        continue
                    inputs.append({
                        "hash": tx['hash'],
                        "id": tx['id'],
                        "index": i,
                        "value": out['value'],
                        "time": tx['time'],
                        "height": tx['height'],
                        "fee": tx['fee'],
                        "public_key": tx['public_key'],
                    })

        spendable = sum(i['value'] for i in inputs)
        print("collected {:,} spendable inputs totaling {:,}"
              .format(len(inputs), spendable))
        if spendable < float(args.value) + 0.01:
            print("insufficient funds")
            sys.exit()

        picked = []
        picked_sum = 0
        for inp in inputs:
            picked.append(inp)
            picked_sum += inp['value']
            if picked_sum >= float(args.value):
                break

        print("picked {:,} inputs totaling {:,} to send for tx"
              .format(len(inputs), spendable))


        transaction = TransactionFactory(
            config,
            mongo,
            block_height=BU.get_latest_block(config, mongo)['index'],
            fee=0.01,
            public_key=config.public_key,
            private_key=config.private_key,
            outputs=[
                {'to': args.to, 'value': float(args.value)}
            ],
            inputs=[
                {"signature": "", "public_key": i['public_key'], "id": i['id']}
                for i in picked],
        )
        print(transaction)

    elif args.mode == 'send':
        Send.run(config, mongo, args.to, float(args.value))

    elif args.mode == 'mine':
        print config.to_json()
        print '\r\n\r\n\r\n//// YADA COIN MINER ////'
        print "Core count:", args.cores
        def get_mine_data():
            try:
                return json.loads(requests.get("http://{pool}/pool".format(pool=args.pool)).content)
            except Exception as e:
                print(e)
                return None
        running_processes = []
        mp = MiningPool(config, mongo)
        while 1:
            Peers.init(config, mongo, args.network, my_peer=False)
            if not Peers.peers:
                time.sleep(1)
                continue
            if len(running_processes) >= int(args.cores):
                for i, proc in enumerate(running_processes):
                    if not proc.is_alive():
                        proc.terminate()
                        data = get_mine_data()
                        if data:
                            p = Process(target=mp.pool_mine, args=(args.pool, config.address, data['header'], data['target'], data['nonces'], data['special_min']))
                            p.start()
                            running_processes[i] = p
            else:
                data = get_mine_data()
                if data:
                    p = Process(target=mp.pool_mine, args=(args.pool, config.address, data['header'], data['target'], data['nonces'], data['special_min']))
                    p.start()
                    running_processes.append(p)
            time.sleep(1)

    elif args.mode == 'faucet':
        while 1:
            Peers.init(config, mongo, args.network)
            if not Peers.peers:
                time.sleep(1)
                continue
            Faucet.run(config, mongo)
            time.sleep(1)

    elif args.mode == 'pool':
        pp = PoolPayer(config, mongo)
        while 1:            
            pp.do_payout()
            time.sleep(1)

    elif args.mode == 'serve':
        print config.to_json()

        config.network = args.network

        my_peer = Peer.init_my_peer(config, mongo, config.network)
        config.callbackurl = 'http://%s/create-relationship' % my_peer.to_string()
        print "http://{}".format(my_peer.to_string())

        serve = Serve(config, mongo)
        serve.socketio.run(serve.app, config.serve_host, config.serve_port)

        

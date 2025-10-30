from datetime import datetime
import hashlib
import json
from pprint import pp
from typing import Dict, List


class Block:
    def __init__(
        self,
        index: int,
        timestamp: str,
        transactions: List,
        prev_hash: str,
        nonce: int,
        hash: str,
    ):
        self.index: int = index
        self.timestamp: str = timestamp
        self.transactions: List = transactions
        self.prev_hash: str = prev_hash
        self.nonce: int = nonce
        self.hash: str = hash

    def as_dict(self) -> Dict:
        """TODO: garantir que dict possui tipo serializável!"""
        return self.__dict__


def create_genesis_block() -> Block:
    gen_block = Block(
        index=0,
        timestamp=str(datetime.utcnow()),
        transactions=[],
        prev_hash="0",
        nonce=0,
        hash="0",
    )
    return gen_block


def create_block_from_dict(block_data: Dict) -> Block:
    return Block(
        index=block_data["index"],
        timestamp=block_data["timestamp"],
        transactions=block_data["transactions"],
        prev_hash=block_data["prev_hash"],
        nonce=block_data["nonce"],
        hash=block_data["hash"],
    )


def create_block(
    transactions: List[Dict],
    prev_hash: str,
    miner: str,
    index: int,
    reward: int,
    difficulty: int,
) -> Block:
    print("[⛏️] Mining block...")
    nonce = 0
    while True:
        coinbase = {"from": "network", "to": miner, "amount": reward}
        all_tx = [coinbase] + transactions

        block = Block(index, str(datetime.utcnow()), all_tx, prev_hash, nonce, "")
        block.hash = hash_block(block)
        if block.hash.startswith("0" * difficulty):
            print(f"[✓] Block mined: {block.hash}")
            return block
        nonce += 1


def hash_block(block: Block) -> str:
    block_copy = dict(block.as_dict())
    block_copy.pop("hash", None)
    print(f"[HASHING] Hashing the block: ")
    pp(block_copy)
    return hashlib.sha256(json.dumps(block_copy, sort_keys=True).encode()).hexdigest()

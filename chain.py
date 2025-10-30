import json
import os
from typing import List

from block import Block, create_block, create_block_from_dict, create_genesis_block, hash_block
from network import broadcast_block, broadcast_transaction


def load_chain(fpath: str) -> List[Block]:
    if os.path.exists(fpath):
        with open(fpath) as f:
            data = json.load(f)
            blockchain = []
            for block_data in data:
                block = create_block_from_dict(block_data)
                blockchain.append(block)
            return blockchain

    return [create_genesis_block()]


def save_chain(fpath: str, chain: list[Block]):
    blockchain_serializable = []
    for b in chain:
        blockchain_serializable.append(b.as_dict())

    with open(fpath, "w") as f:
        json.dump(blockchain_serializable, f, indent=2)


def valid_chain(chain, difficulty: int) -> bool:
    """
    Verifica se uma cadeia é válida.
    chain pode ser lista de Block ou lista de dicts (serializados).
    Verificações:
      - prev_hash de cada bloco coincide com hash do anterior
      - hash do bloco é correto (re-hash)
      - proof-of-work: hash inicia com '0' * difficulty
    """
    # Normaliza para Block objects
    normalized_chain: List[Block] = []
    for b in chain:
        if isinstance(b, dict):
            normalized_chain.append(create_block_from_dict(b))
        elif isinstance(b, Block):
            normalized_chain.append(b)
        else:
            return False

    # Genesis é permitida (índice 0)
    for i in range(1, len(normalized_chain)):
        prev = normalized_chain[i - 1]
        curr = normalized_chain[i]
        # prev_hash link check
        if curr.prev_hash != prev.hash:
            return False
        # hash correctness
        expected = hash_block(curr)
        if curr.hash != expected:
            return False
        # proof-of-work
        if not curr.hash.startswith("0" * difficulty):
            return False
    return True


def print_chain(blockchain: List[Block]):
    for b in blockchain:
        print(f"Index: {b.index}, Hash: {b.hash[:10]}..., Tx: {len(b.transactions)}")


def mine_block(
    transactions: List,
    blockchain: List[Block],
    node_id: str,
    reward: int,
    difficulty: int,
    blockchain_fpath: str,
    peers_fpath: str,
    port: int,
):
    new_block = create_block(
        transactions,
        blockchain[-1].hash,
        miner=node_id,
        index=len(blockchain),
        reward=reward,
        difficulty=difficulty,
    )
    blockchain.append(new_block)
    transactions.clear()
    save_chain(blockchain_fpath, blockchain)
    broadcast_block(new_block, peers_fpath, port)
    print(f"[✓] Block {new_block.index} mined and broadcasted.")


def make_transaction(sender, recipient, amount, transactions, peers_file, port):
    tx = {"from": sender, "to": recipient, "amount": amount}
    transactions.append(tx)
    broadcast_transaction(tx, peers_file, port)
    print("[+] Transaction added.")


def get_balance(node_id: str, blockchain: List[Block]) -> float:
    balance = 0
    for block in blockchain:
        for tx in block.transactions:
            if tx["to"] == node_id:
                balance += float(tx["amount"])
            if tx["from"] == node_id:
                balance -= float(tx["amount"])
    return balance


def on_valid_block_callback(fpath, chain):
    save_chain(fpath, chain)


def resolve_conflicts(local_chain: List[Block], remote_chain_data, difficulty: int, fpath: str):
    """
    Implementa a Longest Chain Rule:
      - remote_chain_data pode ser lista de dicts ou lista de Block
      - se a cadeia remota for mais longa e válida, substitui a cadeia local e salva em disco
    Retorna True se substituiu, False caso contrário.
    """
    # Normaliza remote para Blocks
    remote_chain: List[Block] = []
    for b in remote_chain_data:
        if isinstance(b, dict):
            remote_chain.append(create_block_from_dict(b))
        elif isinstance(b, Block):
            remote_chain.append(b)
        else:
            # tipo inválido
            return False

    if len(remote_chain) <= len(local_chain):
        return False

    if not valid_chain(remote_chain, difficulty):
        return False

    # Substitui conteúdo da lista local para manter referências
    local_chain.clear()
    local_chain.extend(remote_chain)
    save_chain(fpath, local_chain)
    print("[✓] Local chain replaced by a longer valid remote chain.")
    return True

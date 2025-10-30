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


def valid_chain(chain, difficulty: int = None):
    """
    Valida uma cadeia. `chain` pode ser:
    - lista de Block objects
    - lista de dicts (serializada)
    Se `difficulty` for fornecida, também verifica proof-of-work (hash startswith zeros).
    Esta versão:
    - normaliza para lista de dicts;
    - calcula hashes ausentes (preenche) quando possível;
    - verifica prev_hash contra hash calculado do bloco anterior;
    - verifica expected_hash vs hash fornecido;
    - verifica proof-of-work quando difficulty é passada.
    """
    # normalizar para lista de dicts
    normalized = []
    if not chain:
        return False

    if isinstance(chain[0], Block):
        for b in chain:
            normalized.append(b.as_dict())
    else:
        # assume lista de dicts
        normalized = [dict(b) for b in chain]  # copia para permitir modificações

    # garantir que o primeiro bloco tenha hash calculável (genesis ou similar)
    try:
        if not normalized:
            return False
        if not normalized[0].get("hash"):
            temp = create_block_from_dict(normalized[0])
            normalized[0]["hash"] = hash_block(temp)
    except Exception:
        return False

    # verificar continuidade e integridade dos hashes
    for i in range(1, len(normalized)):
        prev = normalized[i - 1]
        cur = normalized[i]

        # garantir que prev tenha hash; calcular se ausente
        if not prev.get("hash"):
            try:
                temp_prev = create_block_from_dict(prev)
                prev["hash"] = hash_block(temp_prev)
            except Exception:
                return False

        # checar link para o bloco anterior
        if cur.get("prev_hash") != prev.get("hash"):
            return False

        # calcular hash esperado a partir dos campos do bloco atual
        try:
            temp_block = create_block_from_dict(cur)
            expected_hash = hash_block(temp_block)
        except Exception:
            return False

        # se o bloco remoto não trouxe 'hash', preenchê-lo com o esperado (aceitar)
        remote_hash = cur.get("hash")
        if not remote_hash:
            cur["hash"] = expected_hash
            remote_hash = expected_hash

        # comparar hashes
        if remote_hash != expected_hash:
            return False

        # verificar proof-of-work se necessário
        if difficulty is not None:
            if not remote_hash.startswith("0" * difficulty):
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
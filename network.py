import json
import os
import socket
import threading
import traceback
from typing import Callable, Dict, List
from block import Block, create_block_from_dict, hash_block


def list_peers(fpath: str):
    if not os.path.exists(fpath):
        print("[!] No peers file founded!")
        return []
    with open(fpath) as f:
        return [line.strip() for line in f if line.strip()]


def broadcast_block(block: Block, peers_fpath: str, port: int):
    print("Broadcasting block...")
    for peer in list_peers(peers_fpath):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((peer, port))
            s.send(json.dumps({"type": "block", "data": block.as_dict()}).encode())
            s.close()
        except Exception:
            pass


def broadcast_transaction(tx: Dict, peers_fpath: str, port: int):
    for peer in list_peers(peers_fpath):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((peer, port))
            s.send(json.dumps({"type": "tx", "data": tx}).encode())
            s.close()
        except Exception as e:
            print(
                f"[BROADCAST_TX] Exception during comunication with {peer}. Exception: {e}"
            )


def handle_client(
        conn: socket.socket,
        addr: str,
        blockchain: List[Block],
        difficulty: int,
        transactions: List[Dict],
        blockchain_fpath: str,
        on_valid_block_callback: Callable,
):
    try:
        data = conn.recv(4096).decode()
        msg = json.loads(data)
        if msg["type"] == "block":
            block = create_block_from_dict(msg["data"])
            expected_hash = hash_block(block)

            # Verifica se o bloco é válido
            if (
                    block.hash.startswith("0" * difficulty)
                    and block.hash == expected_hash
            ):
                # Verifica se já existe um bloco com o mesmo índice
                existing_block_index = None
                for i, existing_block in enumerate(blockchain):
                    if existing_block.index == block.index:
                        existing_block_index = i
                        break

                # Se existe um bloco com o mesmo índice, substitui
                if existing_block_index is not None:
                    blockchain[existing_block_index] = block
                    print(f"[✓] Block {block.index} replaced from {addr}")
                # Se o bloco é sequencial (index correto), adiciona ao final
                elif block.index == len(blockchain):
                    if blockchain and block.prev_hash == blockchain[-1].hash:
                        blockchain.append(block)
                        print(f"[✓] New block {block.index} added from {addr}")
                    else:
                        print(f"[!] Invalid prev_hash in block received from {addr}")
                        conn.close()
                        return
                else:
                    print(f"[!] Invalid block index {block.index} received from {addr}. Expected {len(blockchain)}")
                    conn.close()
                    return

                on_valid_block_callback(blockchain_fpath, blockchain)
            else:
                print(f"[!] Invalid block received from {addr}")
        elif msg["type"] == "tx":
            tx = msg["data"]
            if tx not in transactions:
                transactions.append(tx)
                print(f"[+] Transaction received from {addr}")
    except Exception as e:
        print(
            f"Exception when hadling client. Exception: {e}. {traceback.format_exc()}"
        )
    conn.close()


def start_server(
        host: str,
        port: int,
        blockchain: List[Block],
        difficulty: int,
        transactions: List[Dict],
        blockchain_fpath: str,
        on_valid_block_callback: Callable,
):
    def server_thread():
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((host, port))
        server.listen()
        print(f"[SERVER] Listening on {host}:{port}")
        while True:
            conn, addr = server.accept()
            threading.Thread(
                target=handle_client,
                args=(
                    conn,
                    addr,
                    blockchain,
                    difficulty,
                    transactions,
                    blockchain_fpath,
                    on_valid_block_callback,
                ),
            ).start()

    threading.Thread(target=server_thread, daemon=True).start()
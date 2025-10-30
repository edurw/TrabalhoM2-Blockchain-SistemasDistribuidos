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


def request_chain(peer_ip: str, port: int, timeout: int = 5):
    """
    Conecta ao peer e solicita a cadeia local dele via mensagem 'get_chain'.
    Retorna a cadeia (lista de dicts) ou None em caso de falha.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((peer_ip, port))
        s.send(json.dumps({"type": "get_chain", "data": None}).encode())
        # espera resposta
        data = s.recv(65536).decode()
        s.close()
        if not data:
            return None
        msg = json.loads(data)
        if msg.get("type") == "chain":
            return msg.get("data")
        return None
    except Exception as e:
        print(f"[REQUEST_CHAIN] Exception contacting {peer_ip}:{port} - {e}")
        return None


def handle_client(
    conn: socket.socket,
    addr: str,
    blockchain: List[Block],
    difficulty: int,
    transactions: List[Dict],
    blockchain_fpath: str,
    on_valid_block_callback: Callable,
    peers_fpath: str,
    port: int,
):
    try:
        data = conn.recv(65536).decode()
        if not data:
            conn.close()
            return
        msg = json.loads(data)
        msg_type = msg.get("type")
        if msg_type == "block":
            block = create_block_from_dict(msg["data"])
            expected_hash = hash_block(block)
            if (
                block.prev_hash == blockchain[-1].hash
                and block.hash.startswith("0" * difficulty)
                and block.hash == expected_hash
            ):
                blockchain.append(block)
                on_valid_block_callback(blockchain_fpath, blockchain)
                print(f"[✓] New valid block added from {addr}")
            else:
                print(f"[!] Received block does not extend local chain (maybe fork). Trying to resolve with peer {addr[0]}")
                # Tenta resolver solicitando a cadeia ao peer
                try:
                    remote_chain = request_chain(addr[0], port)
                    if remote_chain:
                        # Importa aqui para evitar circular imports no topo
                        from chain import resolve_conflicts

                        replaced = resolve_conflicts(blockchain, remote_chain, difficulty, blockchain_fpath)
                        if replaced:
                            print(f"[✓] Chain replaced using chain from {addr[0]}")
                        else:
                            print("[i] No replacement performed after requesting remote chain.")
                    else:
                        print("[!] Could not fetch remote chain to resolve conflict.")
                except Exception as e:
                    print(f"[!] Error while requesting remote chain: {e}")
        elif msg_type == "tx":
            tx = msg["data"]
            if tx not in transactions:
                transactions.append(tx)
                print(f"[+] Transaction received from {addr}")
        elif msg_type == "get_chain":
            # O peer quer a nossa chain: responde com type 'chain' e a cadeia serializada
            try:
                payload = [b.as_dict() for b in blockchain]
                conn.send(json.dumps({"type": "chain", "data": payload}).encode())
                print(f"[✓] Responded chain to {addr}")
            except Exception as e:
                print(f"[!] Could not send chain to {addr}: {e}")
        elif msg_type == "chain":
            # Um peer nos enviou a cadeia completa para que possamos tentar resolver conflitos
            try:
                remote_chain = msg.get("data")
                from chain import resolve_conflicts

                replaced = resolve_conflicts(blockchain, remote_chain, difficulty, blockchain_fpath)
                if replaced:
                    on_valid_block_callback(blockchain_fpath, blockchain)
                    print(f"[✓] Local chain replaced by chain received from {addr}")
                else:
                    print("[i] Received chain did not replace local chain.")
            except Exception as e:
                print(f"[!] Error processing received chain from {addr}: {e}")
        else:
            print(f"[!] Unknown message type {msg_type} from {addr}")
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
    peers_fpath: str,
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
                    peers_fpath,
                    port,
                ),
            ).start()

    threading.Thread(target=server_thread, daemon=True).start()
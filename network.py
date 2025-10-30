import json
import os
import socket
import threading
import traceback
from typing import Callable, Dict, List
from block import Block, create_block_from_dict, hash_block
import requests  # novo import para buscar chains via HTTP


def list_peers(fpath: str):
    if not os.path.exists(fpath):
        print("[!] No peers file founded!")
        return []
    with open(fpath) as f:
        return [line.strip() for line in f if line.strip()]


def broadcast_block(block: Block, peers_fpath: str, port: int):
    print("Broadcasting transaction...")
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
    server_port: int,  # novo parâmetro
):
    try:
        raw = conn.recv(65536)
        if not raw:
            # cliente fechou conexão sem enviar dados
            return
        try:
            data = raw.decode()
        except Exception:
            print(f"[!] Failed to decode bytes from {addr}")
            return

        if not data or not data.strip():
            # mensagem vazia
            return

        # --- Novo: tratar requisições HTTP GET (requests.get envia GET) ---
        # Se for um pedido HTTP, responde com a blockchain serializada
        first_line = data.splitlines()[0] if data.splitlines() else ""
        if first_line.startswith("GET "):
            parts = first_line.split()
            path = parts[1] if len(parts) >= 2 else "/"
            endpoints = ["/chain", "/blockchain", "/blockchain.json", "/blocks"]
            if path in endpoints:
                try:
                    chain_list = [b.as_dict() for b in blockchain]
                    payload = json.dumps(chain_list)
                    resp = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: application/json\r\n"
                        f"Content-Length: {len(payload.encode())}\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        f"{payload}"
                    )
                    conn.send(resp.encode())
                except Exception as e:
                    print(f"[!] Error sending chain to {addr}: {e}")
                return
            else:
                # caminho desconhecido
                resp = "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
                try:
                    conn.send(resp.encode())
                except Exception:
                    pass
                return
        # --- Fim tratamento HTTP ---

        # tenta interpretar como JSON (mensagens de peers via socket raw)
        try:
            msg = json.loads(data.strip())
        except json.JSONDecodeError:
            print(f"[!] Received non-JSON or malformed message from {addr}: {data!r}")
            return

        if msg.get("type") == "block":
            block = create_block_from_dict(msg["data"])
            expected_hash = hash_block(block)

            # Primeiro, tenta validar o bloco para o estado atual
            if (
                block.prev_hash == blockchain[-1].hash
                and block.hash.startswith("0" * difficulty)
                and block.hash == expected_hash
            ):
                blockchain.append(block)
                on_valid_block_callback(blockchain_fpath, blockchain)
                print(f"[✓] New valid block added from {addr}")
            else:
                # Se o bloco não é válido para o estado atual, pode ser parte de uma cadeia mais longa
                print(f"[!] Block from {addr} doesn't connect to current chain. Attempting to resolve...")

                # Tentar buscar a cadeia completa do peer via HTTP (usa a porta do servidor)
                try:
                    peer_host = addr[0] if isinstance(addr, tuple) else addr.split(':')[0]
                    peer_port = server_port  # assume peers usam a mesma porta de escuta

                    endpoints = ["/chain", "/blockchain", "/blockchain.json", "/blocks"]
                    remote_chain = None
                    for ep in endpoints:
                        try:
                            url = f"http://{peer_host}:{peer_port}{ep}"
                            resp = requests.get(url, timeout=3)
                            if resp.status_code == 200:
                                try:
                                    data_remote = resp.json()
                                    if isinstance(data_remote, dict) and "chain" in data_remote:
                                        remote_chain = data_remote["chain"]
                                    elif isinstance(data_remote, list):
                                        remote_chain = data_remote
                                    elif isinstance(data_remote, dict) and "blocks" in data_remote and isinstance(data_remote["blocks"], list):
                                        remote_chain = data_remote["blocks"]
                                    if remote_chain is not None:
                                        break
                                except ValueError:
                                    continue
                        except Exception:
                            continue

                    if remote_chain:
                        # importa validadores/carregadores em tempo de execução para evitar import circular
                        from chain import valid_chain, load_chain

                        # validar cadeia remota
                        if not valid_chain(remote_chain, difficulty):
                            print(f"[consensus] Remote chain from {peer_host}:{peer_port} is invalid, ignoring.")
                        else:
                            # decidir adoção: maior comprimento OU tie-breaker (last hash numericamente menor)
                            local_len = len(blockchain)
                            remote_len = len(remote_chain)
                            adopt = False
                            if remote_len > local_len:
                                adopt = True
                            elif remote_len == local_len:
                                try:
                                    remote_last = remote_chain[-1].get("hash")
                                    local_last = blockchain[-1].hash
                                    if remote_last and int(remote_last, 16) < int(local_last, 16):
                                        adopt = True
                                except Exception:
                                    adopt = False

                            if adopt:
                                # substituir arquivo local e recarregar cadeia em memória
                                try:
                                    with open(blockchain_fpath, "w") as f:
                                        json.dump(remote_chain, f, indent=2)
                                    reloaded = load_chain(blockchain_fpath)
                                    blockchain[:] = reloaded
                                    print(f"[consensus] Adopted remote chain from {peer_host}:{peer_port} (len {remote_len}).")
                                    # opcional: persistir via callback
                                    try:
                                        on_valid_block_callback(blockchain_fpath, blockchain)
                                    except Exception:
                                        pass
                                except Exception as e:
                                    print(f"[consensus] Failed to adopt remote chain: {e}")
                            else:
                                print(f"[consensus] Kept local chain (longer/better than {peer_host}:{peer_port}).")
                    else:
                        print(f"[consensus] Could not fetch chain from {peer_host}:{peer_port}")
                except Exception as e:
                    print(f"[!] Failed to resolve chain conflict with {addr}: {e}")

        elif msg.get("type") == "tx":
            tx = msg["data"]
            if tx not in transactions:
                transactions.append(tx)
                print(f"[+] Transaction received from {addr}")
    except Exception as e:
        print(
            f"Exception when hadling client. Exception: {e}. {traceback.format_exc()}"
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass


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
                    port,  # passa a porta do servidor ao handler
                ),
            ).start()

    threading.Thread(target=server_thread, daemon=True).start()

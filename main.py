from typing import Dict, List

from chain import (
    get_balance,
    load_chain,
    make_transaction,
    mine_block,
    on_valid_block_callback,
    print_chain,
)
from network import start_server
from utils import load_config

import requests
import json
import os
import threading
import time


if __name__ == "__main__":
    """
    Exemplo de config:
    {
        "node_id": "george_linux", // nome exclusivo para o computador em que o código será executado
        "host": "172.29.20.2", // IP fornecido pelo zerotier para o computador em que o código será executado
        "port": 5002, // porta padrão estabelecida para toda a rede P2P
        "difficulty": 4, // dificuldade de mineração
        "reward": 10, // recompensa pela mineração
        "blockchain_file": "db/blockchain.json", // arquivo para salvar blockchain
        "peers_file": "configs/peers.txt" // arquivo para listar os IPs dos demais pares
    }
    """
    config = load_config()
    blockchain = load_chain(config["blockchain_file"])
    transactions: List[Dict] = []

    def read_peers(peers_file: str) -> List[Dict[str, str]]:
        """Lê arquivo de peers. Cada linha pode ser 'ip' ou 'ip:port'."""
        peers = []
        if not os.path.exists(peers_file):
            return peers
        with open(peers_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    host, port = line.split(":", 1)
                    peers.append({"host": host.strip(), "port": int(port.strip())})
                else:
                    peers.append({"host": line, "port": config["port"]})
        return peers

    def fetch_chain_from_peer(host: str, port: int) -> List[Dict]:
        """Tenta GET em endpoints comuns e retorna chain (lista de blocos) ou None."""
        endpoints = ["/chain", "/blockchain", "/blockchain.json", "/blocks"]
        for ep in endpoints:
            try:
                url = f"http://{host}:{port}{ep}"
                resp = requests.get(url, timeout=3)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        # Caso a resposta seja um objeto que contenha a chain:
                        if isinstance(data, dict) and "chain" in data:
                            return data["chain"]
                        if isinstance(data, list):
                            return data
                        # se for dict com "blocks" por exemplo
                        if isinstance(data, dict) and "blocks" in data and isinstance(data["blocks"], list):
                            return data["blocks"]
                    except ValueError:
                        continue
            except Exception:
                continue
        return None

    def replace_local_chain_if_longer(local_chain: List[Dict], remote_chain: List[Dict], blockchain_file: str):
        """Substitui o arquivo local se a remote for mais longa."""
        if remote_chain is None:
            return local_chain, False
        try:
            if len(remote_chain) > len(local_chain):
                # grava a cadeia remota localmente
                with open(blockchain_file, "w") as f:
                    json.dump(remote_chain, f, indent=2)
                print(f"[consensus] Replaced local chain with longer remote chain (len {len(remote_chain)}).")
                return remote_chain, True
        except Exception as e:
            print(f"[consensus] Erro ao salvar chain remota: {e}")
        return local_chain, False

    def resolve_conflicts(local_chain: List[Dict], blockchain_file: str, peers_file: str, default_port: int, difficulty: int):
        """
        Implementa Longest Chain Rule com validação:
        - valida chains remotas via chain.valid_chain(..., difficulty)
        - adota cadeia mais longa
        - se empate no comprimento, adota cadeia cujo último hash seja numericamente menor
        """
        peers = read_peers(peers_file)
        # normalizar local_chain para lista de dicts para comparações
        try:
            from chain import valid_chain, load_chain as _load_chain
        except Exception:
            # fallback caso import circular apareça
            valid_chain = None
            _load_chain = None

        # criar uma cópia que será atualizada
        new_chain = local_chain

        for p in peers:
            remote_chain = fetch_chain_from_peer(p["host"], p.get("port", default_port))
            if not remote_chain:
                continue

            # validar cadeia remota se possível
            try:
                if valid_chain is not None and not valid_chain(remote_chain, difficulty):
                    print(f"[consensus] Remote chain from {p['host']}:{p.get('port', default_port)} is invalid, ignoring.")
                    continue
            except Exception as e:
                print(f"[consensus] Error validating remote chain from {p['host']}:{p.get('port', default_port)}: {e}")
                continue

            # normalizar both para lista de dicts (podem ser Block objects localmente)
            def to_dicts(chain):
                if not chain:
                    return []
                # detectar Block objects pelo primeiro item
                first = chain[0]
                if hasattr(first, "as_dict"):
                    return [b.as_dict() for b in chain]
                else:
                    return [dict(b) for b in chain]

            local_norm = to_dicts(new_chain)
            remote_norm = to_dicts(remote_chain)

            local_len = len(local_norm)
            remote_len = len(remote_norm)
            adopt = False

            if remote_len > local_len:
                adopt = True
            elif remote_len == local_len:
                try:
                    remote_last = remote_norm[-1].get("hash")
                    local_last = local_norm[-1].get("hash")
                    if remote_last and local_last and int(remote_last, 16) < int(local_last, 16):
                        adopt = True
                except Exception:
                    adopt = False

            if adopt:
                try:
                    # gravar cadeia remota e recarregar em memória
                    with open(blockchain_file, "w") as f:
                        json.dump(remote_norm, f, indent=2)
                    if _load_chain is not None:
                        reloaded = _load_chain(blockchain_file)
                        new_chain = reloaded
                    else:
                        new_chain = remote_chain
                    print(f"[consensus] Adopted remote chain from {p['host']}:{p.get('port', default_port)} (len {remote_len}).")
                except Exception as e:
                    print(f"[consensus] Failed to adopt remote chain from {p['host']}:{p.get('port', default_port)}: {e}")

        return new_chain

    # Thread de sincronização periódica: chama resolve_conflicts e atualiza blockchain em-place
    def start_periodic_sync(interval_seconds: int = 3):
        def worker():
            while True:
                try:
                    new_chain = resolve_conflicts(blockchain, config["blockchain_file"], config["peers_file"], config["port"], config["difficulty"])
                    if new_chain:
                        try:
                            # atualiza em-place para preservar referências
                            blockchain[:] = new_chain
                        except Exception:
                            # fallback removido para evitar UnboundLocalError
                            pass
                except Exception as e:
                    print(f"[sync] Error during periodic sync: {e}")
                time.sleep(interval_seconds)

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    start_server(
        config["host"],
        config["port"],
        blockchain,
        config["difficulty"],
        transactions,
        config["blockchain_file"],
        on_valid_block_callback,
    )

    # iniciar sincronização periódica para convergência automática entre peers
    start_periodic_sync(interval_seconds=3)

    # Ao iniciar, tentar resolver conflitos (adotar cadeia mais longa)
    blockchain = resolve_conflicts(blockchain, config["blockchain_file"], config["peers_file"], config["port"], config["difficulty"])

    print("=== SimpleCoin CLI ===")
    while True:
        print("\n1. Add transaction")
        print("2. Mine block")
        print("3. View blockchain")
        print("4. Get balance")
        print("5. Exit")
        choice = input("> ").strip()

        if choice == "1":
            sender = input("Sender: ")
            recipient = input("Recipient: ")
            amount = input("Amount: ")
            make_transaction(
                sender,
                recipient,
                amount,
                transactions,
                config["peers_file"],
                config["port"],
            )

        elif choice == "2":
            # Antes de minerar, garantir que estamos na maior cadeia possível
            blockchain = resolve_conflicts(blockchain, config["blockchain_file"], config["peers_file"], config["port"], config["difficulty"])

            mine_block(
                transactions,
                blockchain,
                config["node_id"],
                config["reward"],
                config["difficulty"],
                config["blockchain_file"],
                config["peers_file"],
                config["port"],
            )

            # Após minerar, verificar se algum peer tem cadeia mais longa (conflito simultâneo)
            blockchain = resolve_conflicts(blockchain, config["blockchain_file"], config["peers_file"], config["port"], config["difficulty"])

        elif choice == "3":
            # Opcional: antes de mostrar, sincronizar
            blockchain = resolve_conflicts(blockchain, config["blockchain_file"], config["peers_file"], config["port"], config["difficulty"])
            print_chain(blockchain)

        elif choice == "4":
            node_id = input("Node ID: ")
            balance = get_balance(node_id, blockchain)
            print(f"[i] The balance of {node_id} is {balance}.")

        elif choice == "5":
            print("Exiting...")
            break

        else:
            print("[!] Invalid choice.")

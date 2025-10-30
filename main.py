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
                        if isinstance(data, dict) and "chain" in data:
                            return data["chain"]
                        if isinstance(data, list):
                            return data
                        if isinstance(data, dict) and "blocks" in data and isinstance(data["blocks"], list):
                            return data["blocks"]
                    except ValueError:
                        continue
            except Exception:
                continue
        return None

    def resolve_conflicts(local_chain, blockchain_file: str, peers_file: str, default_port: int, difficulty: int):
        """
        Implementa a Longest Chain Rule com tie-breaker:
        - adota cadeia mais longa
        - se empates no comprimento, adota a cadeia cujo last-hash seja numericamente menor
        Valida a cadeia remota antes de adotá-la.
        Aceita tanto lista de Block quanto lista de dicts.
        """
        # Normalizar para lista serializável de dicts ao calcular comprimentos/hashes
        def to_dict_list(chain):
            if not chain:
                return []
            from block import Block as _Block
            if isinstance(chain[0], _Block):
                return [b.as_dict() for b in chain]
            return [dict(b) for b in chain]

        peers = read_peers(peers_file)
        current_dict_chain = to_dict_list(local_chain)
        replaced = False

        from chain import valid_chain, load_chain as _load_chain

        for p in peers:
            remote_chain = fetch_chain_from_peer(p["host"], p.get("port", default_port))
            if not remote_chain:
                continue

            try:
                if not valid_chain(remote_chain, difficulty):
                    print(f"[consensus] Remote chain from {p['host']}:{p.get('port', default_port)} is invalid, ignoring.")
                    continue
            except Exception as e:
                print(f"[consensus] Error validating remote chain from {p['host']}:{p.get('port', default_port)}: {e}")
                continue

            local_len = len(current_dict_chain)
            remote_len = len(remote_chain)
            adopt = False

            if remote_len > local_len:
                adopt = True
            elif remote_len == local_len and remote_len > 0:
                try:
                    remote_last = remote_chain[-1].get("hash")
                    local_last = current_dict_chain[-1].get("hash")
                    if remote_last and local_last and int(remote_last, 16) < int(local_last, 16):
                        adopt = True
                except Exception:
                    adopt = False

            if adopt:
                try:
                    with open(blockchain_file, "w") as f:
                        json.dump(remote_chain, f, indent=2)
                    reloaded = _load_chain(blockchain_file)
                    current_dict_chain = [b.as_dict() for b in reloaded]
                    replaced = True
                    print(f"[consensus] Adopted remote chain from {p['host']}:{p.get('port', default_port)} (len {remote_len}).")
                except Exception as e:
                    print(f"[consensus] Failed to adopt remote chain from {p['host']}:{p.get('port', default_port)}: {e}")

        if replaced:
            try:
                reloaded = _load_chain(blockchain_file)
                return reloaded
            except Exception as e:
                print(f"[consensus] Falha ao recarregar blockchain: {e}")
        return local_chain

    start_server(
        config["host"],
        config["port"],
        blockchain,
        config["difficulty"],
        transactions,
        config["blockchain_file"],
        on_valid_block_callback,
    )

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

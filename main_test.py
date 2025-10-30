from typing import Dict, List

from chain import load_chain, make_transaction, mine_block
from network import start_server
from utils import load_config



if __name__ == "__main__":
    config = load_config()
    blockchain = load_chain(config["blockchain_file"])
    transactions: List[Dict] = []

    start_server(
        config["host"],
        config["port"],
        blockchain,
        config["difficulty"],
        transactions,
        config["blockchain_file"],
        config.get("peers_file", "configs/peers.txt"),
    )

    # create a transaction
    print("[TEST] Make transaction")
    make_transaction(
        "george_linux",
        "george_windows",
        10,
        transactions,
        config["peers_file"],
        config["port"],
    )

    print("[TEST] Mine block")
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
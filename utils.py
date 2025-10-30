import json
from pprint import pp
from typing import Dict


def load_config(fpath: str = "configs/node_config.json") -> Dict:
    print("Loading config...")
    with open(fpath, "r") as f:
        data = json.load(f)
        print("Config loaded:")
        pp(data)
        return data

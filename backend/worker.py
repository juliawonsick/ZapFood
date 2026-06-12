import os
import sys

os.environ["ZAPFOOD_EMBEDDED_WORKER"] = "0"
sys.path.insert(0, os.path.dirname(__file__))

import main


if __name__ == "__main__":
    main.db.init_db()
    main.cache_cardapio()
    print("[WORKER] Consumidor independente iniciado")
    main.consumer_loop()

"""Atualiza o cadastro pela API; pode ser chamado por um agendador."""
import argparse
import os

import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewed-sha256")
    args = parser.parse_args()
    url = os.environ.get("API_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
    token = os.environ.get("INTERNAL_TOKEN")
    if not token:
        parser.error("Configure INTERNAL_TOKEN no ambiente.")
    payload = {"reviewed_sha256": args.reviewed_sha256} if args.reviewed_sha256 else {}
    response = requests.post(url + "/bet_registry/sync", json=payload,
                             headers={"INTERNAL-TOKEN": token}, timeout=60)
    print(response.text)
    response.raise_for_status()


if __name__ == "__main__":
    main()

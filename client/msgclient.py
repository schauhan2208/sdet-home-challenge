"""Python client + CLI for the message server.

CLI:  python -m client.msgclient send "hello"   |  list [--json]  |  delete 3
Env:  MSG_URL, MSG_USER, MSG_PASS, MSG_INSECURE=1 (accept self-signed TLS)
"""
import argparse
import json
import os
import sys

import requests


class MessageClient:
    def __init__(self, base_url="http://localhost:8000", user=None, password=None,
                 verify=True, timeout=10):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.verify = verify
        if user:
            self.session.auth = (user, password or "")
        self.timeout = timeout

    def _req(self, method, path, **kw):
        resp = self.session.request(method, self.base_url + path, timeout=self.timeout, verify=self.verify, **kw)
        resp.raise_for_status()
        return resp

    def send(self, message: str) -> dict:
        return self._req("POST", "/messages", json={"message": message}).json()

    def list(self) -> list[dict]:
        return self._req("GET", "/messages").json()

    def delete(self, msg_id: int) -> None:
        self._req("DELETE", f"/messages/{msg_id}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="msgclient")
    p.add_argument("--url", default=os.environ.get("MSG_URL", "http://localhost:8000"))
    p.add_argument("--user", default=os.environ.get("MSG_USER"))
    p.add_argument("--password", default=os.environ.get("MSG_PASS"))
    p.add_argument("--insecure", action="store_true", default=bool(os.environ.get("MSG_INSECURE")),
                   help="skip TLS verification (self-signed certs)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("send"); s.add_argument("message")
    l = sub.add_parser("list"); l.add_argument("--json", action="store_true")
    d = sub.add_parser("delete"); d.add_argument("id", type=int)
    args = p.parse_args(argv)

    c = MessageClient(args.url, args.user, args.password, verify=not args.insecure)
    try:
        if args.cmd == "send":
            print(json.dumps(c.send(args.message)))
        elif args.cmd == "list":
            msgs = c.list()
            if args.json:
                print(json.dumps(msgs))
            else:
                for m in msgs:
                    print(f"{m['id']}\t{m['created_at']}\t{m['message']}")
        else:
            c.delete(args.id)
    except requests.RequestException as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

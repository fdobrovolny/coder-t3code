#!/usr/bin/env python3
"""Mint a T3 pairing link for the workspace's externally reachable origin."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen

QR_WHEEL = (
    "https://files.pythonhosted.org/packages/dd/b8/"
    "d2d6d731733f51684bbf76bf34dab3b70a9148e8f2cef2bb544fccec681a/"
    "qrcode-8.2-py3-none-any.whl"
)
QR_SHA256 = "16e64e0716c14960108e85d853062c9e8bba5ca8252c0b4d0231b9df4060ff4f"


def pairing_origin(override):
    if not override:
        proxy = os.environ.get("VSCODE_PROXY_URI", "")
        if "{{port}}" not in urlsplit(proxy).netloc:
            raise ValueError(
                "Coder did not provide a subdomain proxy URL. "
                "Set T3CODE_PAIR_ORIGIN to your T3 Code Web origin."
            )
        override = proxy.replace("{{port}}", "t3code-web", 1)

    url = urlsplit(override)
    if (
        url.scheme not in ("http", "https")
        or not url.hostname
        or url.username is not None
        or url.path not in ("", "/")
        or any(char.isspace() or char in "?#\\{}" for char in override)
    ):
        raise ValueError(
            "Pairing requires an HTTP(S) origin with no credentials, path, query, or fragment."
        )
    if url.port == 0:
        raise ValueError("Pairing requires a valid port.")
    return f"{url.scheme}://{url.netloc}"


def render_qr(url):
    try:
        import qrcode
    except ModuleNotFoundError:
        with tempfile.TemporaryDirectory() as directory:
            with urlopen(QR_WHEEL, timeout=10) as response:
                wheel = response.read()
            if hashlib.sha256(wheel).hexdigest() != QR_SHA256:
                raise ValueError("The QR renderer download failed its checksum.")
            wheel_path = os.path.join(directory, "qrcode.whl")
            with open(wheel_path, "wb") as output:
                output.write(wheel)
            sys.path.insert(0, wheel_path)
            try:
                import qrcode
            finally:
                sys.path.pop(0)

    qr = qrcode.QRCode(border=4)
    qr.add_data(url)
    qr.print_ascii(tty=sys.stdout.isatty())


def terminal_link(url):
    if not sys.stdout.isatty():
        return url
    return f"\x1b]8;;{url}\x1b\\{url}\x1b]8;;\x1b\\"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default=os.environ.get("T3CODE_PAIR_ORIGIN"))
    parser.add_argument("--port", type=int, default=3773, help="local T3 Code server port")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    try:
        origin = pairing_origin(args.origin)
    except ValueError as error:
        parser.error(str(error))

    try:
        with urlopen(f"http://127.0.0.1:{args.port}/.well-known/t3/environment", timeout=3):
            pass
    except OSError:
        parser.exit(
            1, f"T3 Code is not responding on port {args.port}. Check the workspace startup logs.\n"
        )

    try:
        issued = subprocess.run(
            ["t3", "auth", "pairing", "create", "--base-url", origin, "--ttl", "5m", "--json"],
            stdout=subprocess.PIPE,
            text=True,
            check=True,
        )
        pairing = json.loads(issued.stdout)
        url, token = pairing["pairUrl"], pairing["credential"]
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError):
        parser.exit(
            1, "Could not create a T3 Code pairing token. Check the CLI installation and version.\n"
        )

    try:
        render_qr(url)
    except (OSError, ImportError, ValueError) as error:
        print(
            f"QR code unavailable ({error}). Use the pairing URL or enter the server and token manually.",
            file=sys.stderr,
        )

    print(f"\nPairing URL: {terminal_link(url)}\nServer: {origin}\nToken:\n{token}")


if __name__ == "__main__":
    main()

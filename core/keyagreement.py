#!/usr/bin/env python3
"""
keyagreement.py — KeyAgreement LinkAja (DH klasik, pure python).


DH (Diffie-Hellman) klasik:
  P = 3072-bit MODP prime (RFC 3526 group 15)
  g = 2
  privateKey = BigInteger(1, SecureRandom(400 bytes))          # 400 byte
  publicKey  = (g ^ priv) mod P   -> hex -> pad "0" ke 768
  sharedKey  = (peerPub ^ priv) mod P -> hex -> pad "0" ke 768

Flow:
  1. getKey() -> {Krisna, Endhy, Rilvi} = 3 private key (hex)
  2. getPublicKey(privKey) -> {Krisna,Endhy,Rilvi} = 3 public key (hex 768)
  3. POST echo {Krisna,Endhy,Rilvi} -> server {x1,x2,x3} (public key server)
  4. getSharedKey(privKey, serverKey) -> {k1,k2,k3} = 768-hex shared secret
  5. k1/k2/k3 dipakai di ExternalFun.encryptJson
"""
from __future__ import annotations
import secrets

# prime DH standar (RFC 3526, 1536-bit)
P_HEX = ("FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AAAC42DAD33170D04507A33A85521ABDF1CBA64ECFB850458DBEF0A8AEA71575D060C7DB3970F85A6E1E4C7ABF5AE8CDB0933D71E8C94E04A25619DCEE3D2261AD2EE6BF12FFA06D98A0864D87602733EC86A64521F2B18177B200CBBE117577A615D6C770988C0BAD946E208E24FA074E5AB3143DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF")
P = int(P_HEX, 16)
G = 2
HEX_LEN = 768          # DEFAULT_LENGTH_HEX
PRIV_BYTES = 400       # 0x190


def _pad(hexstr: str, n: int = HEX_LEN) -> str:
    """formatHexString: pad kiri pakai '0' sampai panjang n."""
    if len(hexstr) < n:
        hexstr = "0" * (n - len(hexstr)) + hexstr
    return hexstr


def generate_private_key() -> str:
    """BigInteger(1, SecureRandom(400 bytes)).toString(16)."""
    b = secrets.token_bytes(PRIV_BYTES)
    v = int.from_bytes(b, "big")           # sign=1, big-endian
    return format(v, "x")


def generate_public_key(priv_hex: str) -> str:
    """(g ^ priv) mod P -> hex -> pad 768."""
    priv = int(priv_hex, 16)
    pub = pow(G, priv, P)
    return _pad(format(pub, "x"))


def generate_shared_key(priv_hex: str, peer_pub_hex: str) -> str:
    """(peerPub ^ priv) mod P -> hex -> pad 768."""
    priv = int(priv_hex, 16)
    peer = int(peer_pub_hex, 16)
    shared = pow(peer, priv, P)
    return _pad(format(shared, "x"))


def get_key() -> dict:
    """3 private key baru."""
    return {
        "key1": generate_private_key(),
        "key2": generate_private_key(),
        "key3": generate_private_key(),
    }


def get_public_key(priv: dict) -> dict:
    return {
        "key1": generate_public_key(priv["key1"]),
        "key2": generate_public_key(priv["key2"]),
        "key3": generate_public_key(priv["key3"]),
    }


def get_shared_key(priv: dict, server_pub: dict) -> dict:
    """priv = private lokal; server_pub = x1/x2/x3 dari server."""
    return {
        "key1": generate_shared_key(priv["key1"], server_pub["key1"]),
        "key2": generate_shared_key(priv["key2"], server_pub["key2"]),
        "key3": generate_shared_key(priv["key3"], server_pub["key3"]),
    }


if __name__ == "__main__":
    # SELF-TEST: dua pihak, shared harus sama dua arah
    a = get_key(); b = get_key()
    a_pub = get_public_key(a); b_pub = get_public_key(b)
    a_shared = get_shared_key(a, b_pub)
    b_shared = get_shared_key(b, a_pub)
    print("P bits:", P.bit_length())
    print("pub1 len:", len(a_pub["key1"]))
    print("shared match a->b == b->a:", a_shared["key1"] == b_shared["key1"])
    print("shared1 (768):", a_shared["key1"])
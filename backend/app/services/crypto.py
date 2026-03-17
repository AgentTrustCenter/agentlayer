from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, utils
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption


def canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def b64encode_bytes(value: bytes) -> str:
    return base64.b64encode(value).decode("utf-8")


def b64decode_text(value: str) -> bytes:
    return base64.b64decode(value.encode("utf-8"))


def fingerprint_public_key(public_key_pem: str) -> str:
    digest = hashlib.sha256(public_key_pem.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def load_or_create_platform_signing_key(path: Path) -> ed25519.Ed25519PrivateKey:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)

    key = ed25519.Ed25519PrivateKey.generate()
    pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    path.write_bytes(pem)
    return key


def get_platform_public_key_pem(private_key: ed25519.Ed25519PrivateKey) -> str:
    public_key = private_key.public_key()
    pem = public_key.public_bytes(Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return pem.decode("utf-8")


def sign_platform_payload(private_key: ed25519.Ed25519PrivateKey, payload: Any) -> str:
    return b64encode_bytes(private_key.sign(canonical_json(payload)))


def verify_platform_signature(public_key_pem: str, payload: Any, signature_b64: str) -> bool:
    public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    signature = b64decode_text(signature_b64)

    try:
        if isinstance(public_key, ed25519.Ed25519PublicKey):
            public_key.verify(signature, canonical_json(payload))
            return True
    except InvalidSignature:
        return False

    raise ValueError("Unsupported platform public key type.")


def _coerce_ecdsa_signature(signature_bytes: bytes) -> bytes:
    if len(signature_bytes) != 64:
        return signature_bytes
    midpoint = len(signature_bytes) // 2
    r = int.from_bytes(signature_bytes[:midpoint], "big")
    s = int.from_bytes(signature_bytes[midpoint:], "big")
    return utils.encode_dss_signature(r, s)


def verify_agent_signature(public_key_pem: str, payload: Any, signature_b64: str) -> bool:
    public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    signature = b64decode_text(signature_b64)
    message = canonical_json(payload)

    try:
        if isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(_coerce_ecdsa_signature(signature), message, ec.ECDSA(hashes.SHA256()))
            return True
        if isinstance(public_key, ed25519.Ed25519PublicKey):
            public_key.verify(signature, message)
            return True
    except InvalidSignature:
        return False

    raise ValueError("Unsupported agent public key type.")

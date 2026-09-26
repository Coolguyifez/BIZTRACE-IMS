import base64

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization


def base64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


# =========================================================
# GENERATE P-256 VAPID KEY
# =========================================================

private_key = ec.generate_private_key(
    ec.SECP256R1()
)

public_key = private_key.public_key()


# =========================================================
# PRIVATE KEY
# =========================================================

private_der = private_key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption()
)


# =========================================================
# PUBLIC KEY
# =========================================================

public_raw = public_key.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint
)


# =========================================================
# OUTPUT
# =========================================================

vapid_private_key = base64url(
    private_der
)

vapid_public_key = base64url(
    public_raw
)


print()
print("=" * 70)
print("VAPID PRIVATE KEY")
print("=" * 70)
print(vapid_private_key)

print()
print("=" * 70)
print("VAPID PUBLIC KEY")
print("=" * 70)
print(vapid_public_key)

print()
print("=" * 70)
print("VAPID SUBJECT")
print("=" * 70)
print("mailto:your-email@example.com")

print()
print("=" * 70)
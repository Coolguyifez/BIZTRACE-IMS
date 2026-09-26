import os
import base64

from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization


load_dotenv()


private_key = os.getenv("VAPID_PRIVATE_KEY", "")

print("Private key exists:", bool(private_key))
print("Private key length:", len(private_key))

try:
    # Restore Base64URL padding
    padded = private_key + "=" * (-len(private_key) % 4)

    der_data = base64.urlsafe_b64decode(padded)

    print("Decoded DER length:", len(der_data))

    key = serialization.load_der_private_key(
        der_data,
        password=None,
    )

    print("Private key type:", type(key).__name__)
    print("VAPID private key: VALID")

except Exception as exc:
    print("VAPID private key: INVALID")
    print(type(exc).__name__ + ":", exc)
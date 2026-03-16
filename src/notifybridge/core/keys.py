from __future__ import annotations

import secrets
import string


ALPHABET = string.ascii_lowercase + string.ascii_uppercase + string.digits


def generate_api_key(length: int = 20) -> str:
    """Generate a random API key string.

    Inputs:
    - `length`: required key length.

    Outputs:
    - Random alphanumeric key string of the requested length.
    """
    return "".join(secrets.choice(ALPHABET) for _ in range(length))

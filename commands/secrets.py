import secrets
import string

from passlib.hash import pbkdf2_sha512

# Special characters safe to embed in a Postgres password.
#
# `$` is deliberately excluded. Generated passwords get rendered into docker compose files,
# and compose interpolates `$VAR` / `${VAR}` in the file itself before creating the container:
# a literal `$` is silently swallowed and the app receives a mangled value, with nothing but a
# "variable is not set" warning to show for it. Escaping it as `$$` per call site was the
# alternative, but it only has to be forgotten once -- and jinja's `|replace` can't do it,
# because a SecretString expands only via __str__ (it would rewrite the op:// reference
# instead). Keeping `$` out of the alphabet entirely removes the failure mode.
SPECIAL_CHARS = "!()?=^_;:,.-"

# Authelia hashes OIDC client secrets with pbkdf2-sha512 at 310000 rounds; matching
# that rounds value makes generated hashes indistinguishable from Authelia's own output.
AUTHELIA_PBKDF2_ROUNDS = 310000


def generate_random_password(length: int = 20) -> str:
    """Generate a random password guaranteed to contain lower/upper/digit/special chars."""
    alphabet = string.ascii_letters + string.digits + SPECIAL_CHARS
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in SPECIAL_CHARS for c in password)
        ):
            return password


def generate_client_secret(length: int = 72) -> str:
    """Generate an OIDC client secret from the rfc3986 unreserved-alphanumeric charset."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def pbkdf2_sha512_hash(secret: str) -> str:
    """Hash a secret the way Authelia does: pbkdf2-sha512 at 310000 rounds."""
    return pbkdf2_sha512.using(rounds=AUTHELIA_PBKDF2_ROUNDS).hash(secret)

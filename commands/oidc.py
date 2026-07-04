from pathlib import Path

import cyclopts
from onepassword.types import ItemCategory, ItemFieldType

from commands.onepassword import create_item
from commands.secrets import generate_client_secret, pbkdf2_sha512_hash
from commands.source_edit import append_to_list

oidc = cyclopts.App(name="oidc")

ROOT = Path(__file__).parent.parent.resolve()
VARS_FILE = ROOT / "deploys" / "docker_vm" / "proxies" / "vars.py"

DEFAULT_SCOPES = ["openid", "groups", "email", "profile"]


def _render_client(
    client_id: str,
    name: str,
    secret_hash: str,
    policy: str,
    redirect_url: str,
    scopes: list[str],
    auth_method: str,
    claims_policy: str | None,
    pkce: bool,
) -> str:
    """Render an oidc_clients dict entry matching the existing 4-space-indented style."""
    scopes_literal = "[" + ", ".join(f'"{s}"' for s in scopes) + "]"
    lines = [
        "    {",
        f'        "id": "{client_id}",',
        f'        "name": "{name}",',
        f'        "secret_hash": "{secret_hash}",',
        f'        "policy": "{policy}",',
        f'        "redirect_uris": ["{redirect_url}"],',
        f'        "scopes": {scopes_literal},',
        f'        "auth_method": "{auth_method}",',
    ]
    if claims_policy is not None:
        lines.append(f'        "claims_policy": "{claims_policy}",')
    if pkce:
        lines.append('        "require_pkce": True,')
        lines.append('        "pkce_challenge_method": "S256",')
    lines.append("    },")
    return "\n".join(lines) + "\n"


@oidc.command
def add_client(
    name: str,
    redirect_url: str,
    *,
    policy: str = "two_factor",
    auth_method: str = "client_secret_basic",
    scopes: list[str] | None = None,
    claims_policy: str | None = None,
    pkce: bool = False,
    dry_run: bool = False,
):
    """Add an Authelia OIDC client to the pyinfra config and create its 1Password item.

    Parameters
    ----------
    name
        Display name (e.g. `Technitium DNS`). The client id is a slug of this.
    redirect_url
        The client's redirect URI.
    policy
        Authelia authorization_policy (`two_factor` or `one_factor`).
    auth_method
        token_endpoint_auth_method (`client_secret_basic` or `client_secret_post`).
    scopes
        OIDC scopes. Defaults to openid/groups/email/profile.
    claims_policy
        Optional claims policy name (e.g. `default`) to restore claims into the ID token.
    pkce
        Require PKCE with the S256 challenge method.
    dry_run
        Print the edited file instead of writing it, and skip creating the item.
    """
    scopes = scopes or DEFAULT_SCOPES
    client_id = name.lower().replace(" ", "-")
    raw_secret = generate_client_secret()
    secret_hash = pbkdf2_sha512_hash(raw_secret)

    item_title = f"{name} OIDC client"
    op_ref = f"op://Homelab/{item_title}/password"

    entry = _render_client(
        client_id=client_id,
        name=name,
        secret_hash=secret_hash,
        policy=policy,
        redirect_url=redirect_url,
        scopes=scopes,
        auth_method=auth_method,
        claims_policy=claims_policy,
        pkce=pkce,
    )
    append_to_list(VARS_FILE, "oidc_clients", entry, dry_run=dry_run)

    print(f"OIDC client '{client_id}' added to the pyinfra config ✅")
    print(f"1Password reference: {op_ref}")

    if dry_run:
        print(f"[dry run] would create 1Password item '{item_title}'")
        print(f"[dry run] generated client secret: {raw_secret}")
        return

    create_item(
        item_title,
        fields=[("password", ItemFieldType.CONCEALED, raw_secret)],
        category=ItemCategory.LOGIN,
    )

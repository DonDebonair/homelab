import asyncio
import os

from onepassword.client import Client
from onepassword.types import (
    ItemCategory,
    ItemCreateParams,
    ItemField,
    ItemFieldType,
)

VAULT_NAME = "Homelab"
INTEGRATION_NAME = "Homelab Secrets Integration"
INTEGRATION_VERSION = "v1.0.0"

# A field is (id, field_type, value). The id doubles as the field title. The 1Password
# SDK / op:// references resolve by field *id*, not display label, so ids like "password"
# and "username" must be exact for the deploy-time SecretString lookups to work.
Field = tuple[str, ItemFieldType, str]


async def _create(title: str, fields: list[Field], category: ItemCategory) -> None:
    token = os.environ["OP_SERVICE_ACCOUNT_TOKEN"]
    client = await Client.authenticate(
        auth=token,
        integration_name=INTEGRATION_NAME,
        integration_version=INTEGRATION_VERSION,
    )
    vaults = await client.vaults.list()
    vault = next(v for v in vaults if v.title == VAULT_NAME)
    await client.items.create(
        ItemCreateParams(
            category=category,
            vault_id=vault.id,
            title=title,
            fields=[
                ItemField(id=fid, title=fid, field_type=ftype, value=value)
                for fid, ftype, value in fields
            ],
        )
    )


def create_item(
    title: str,
    fields: list[Field],
    category: ItemCategory = ItemCategory.LOGIN,
) -> bool:
    """Create a 1Password item in the Homelab vault.

    Returns True on success. On any failure (read-only token, duplicate item, missing
    vault, ...) prints a warning plus the secret values and their op:// references so the
    operator can create the item manually, then returns False.
    """
    try:
        asyncio.run(_create(title, fields, category))
        print(f"1Password item '{title}' created in vault '{VAULT_NAME}' ✅")
        return True
    except Exception as exc:  # noqa: BLE001 — surface everything as a manual-entry fallback
        print(f"⚠️  Could not create 1Password item '{title}': {exc}")
        print("   Create it manually with these fields:")
        for fid, _ftype, value in fields:
            print(f"     op://{VAULT_NAME}/{title}/{fid} = {value}")
        return False

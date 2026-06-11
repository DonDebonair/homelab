import os
from collections.abc import Iterable
from passlib.hash import sha512_crypt

from onepassword.client import Client

OP_INTEGRATION_NAME = "Homelab Secrets Integration"
OP_INTEGRATION_VERFSION = "v1.0.0"

class SecretString(str):
    _lookup_table: dict[str, str] = {}
    _pending_references: set[str] = set()
    _op_client_instance: Client = None

    def __new__(cls, reference: str):
        obj = super().__new__(cls, reference)
        obj._reference = reference
        cls._pending_references.add(reference)
        return obj

    def encrypted(self, salt: str | None = None) -> str:
        if salt is None:
            passwd_hash = sha512_crypt.hash(self._get_value())
        else:
            salt = str(salt)
            hasher = sha512_crypt.using(salt=salt)
            passwd_hash = hasher.hash(self._get_value())
        return passwd_hash

    @classmethod
    async def get_client(cls):
        if cls._op_client_instance is None:
            op_client_token = os.getenv("OP_SERVICE_ACCOUNT_TOKEN")
            cls._client_instance = await Client.authenticate(
                auth=op_client_token,
                integration_name=OP_INTEGRATION_NAME,
                integration_version=OP_INTEGRATION_VERFSION
            )
        return cls._client_instance

    @classmethod
    async def populate_cache(cls):
        if not cls._pending_references:
            return
        await cls._fetch_and_set_cache(cls._pending_references)
        cls._pending_references.clear()

    @classmethod
    def populate_cache_sync(cls):
        import asyncio
        asyncio.run(cls.populate_cache())

    @classmethod
    async def refresh_cache(cls):
        all_keys = set(cls._lookup_table) | cls._pending_references
        if not all_keys:
            return
        await cls._fetch_and_set_cache(all_keys)
        cls._pending_references.clear()

    @classmethod
    async def _fetch_and_set_cache(cls, references: Iterable[str]):
        client = await cls.get_client()
        fetched_secrets = await client.secrets.resolve_all(list(references))
        updates = {ref: response.content.secret for ref, response in fetched_secrets.individual_responses.items()}
        cls._lookup_table.update(updates)

    async def refresh(self):
        client = await self.__class__.get_client()
        updated = await client.secrets.resolve(self._reference)
        self.__class__._lookup_table[self._reference] = updated

    def _get_value(self):
        return self._lookup_table.get(self._reference, f"<unknown:{self._reference}>")

    @classmethod
    def get_pending_references(cls):
        return cls._pending_references

    @classmethod
    def get_lookup_table(cls):
        return cls._lookup_table

    def __str__(self):
        return self._get_value()

    def __repr__(self):
        return f"SecretString({repr(self._reference)})"

    def __add__(self, other):
        return self._get_value() + str(other)

    def __radd__(self, other):
        return str(other) + self._get_value()

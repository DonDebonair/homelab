from pathlib import Path

import cyclopts
from onepassword.types import ItemCategory, ItemFieldType

from commands.onepassword import create_item
from commands.secrets import generate_random_password
from commands.source_edit import append_secret, append_to_list

db = cyclopts.App(name="db")

ROOT = Path(__file__).parent.parent.resolve()
VARS_FILE = ROOT / "deploys" / "postgres_lxc" / "databases" / "vars.py"
SECRETS_FILE = ROOT / "deploys" / "postgres_lxc" / "databases" / "secrets.py"


@db.command
def add_db(
    name: str,
    user: str | None = None,
    display_name: str | None = None,
    dry_run: bool = False,
):
    """Add a PostgreSQL database + user to the pyinfra config and create its 1Password item.

    Parameters
    ----------
    name
        Lowercase database/user name (e.g. `nocodb`).
    user
        Owning role. Defaults to `name`.
    display_name
        Display-cased app name used in the 1Password item title
        (e.g. `NocoDB`). Defaults to `name.capitalize()`.
    dry_run
        Print the edited files instead of writing them, and skip creating the item.
    """
    user = user or name
    display = display_name or name.capitalize()
    password = generate_random_password()

    item_title = f"PostgreSQL {display} user"
    op_ref = f"op://Homelab/{item_title}/password"
    secret_var = f"{name}_password"

    append_secret(
        SECRETS_FILE,
        f'{secret_var} = SecretString("{op_ref}")',
        dry_run=dry_run,
    )
    append_to_list(
        VARS_FILE,
        "databases",
        f'    PostgresDBConfig(name="{name}", user="{user}", password=str(secrets.{secret_var})),\n',
        dry_run=dry_run,
    )

    print(f"Database '{name}' (user '{user}') added to the pyinfra config ✅")
    print(f"1Password reference: {op_ref}")

    if dry_run:
        print(f"[dry run] would create 1Password item '{item_title}'")
        print(f"[dry run] generated DB password: {password}")
        return

    create_item(
        item_title,
        fields=[
            ("username", ItemFieldType.TEXT, user),
            ("password", ItemFieldType.CONCEALED, password),
        ],
        category=ItemCategory.DATABASE,
    )

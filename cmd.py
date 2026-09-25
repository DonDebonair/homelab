#!/usr/bin/env python

import cyclopts

from commands.db import db
from commands.n8n import n8n
from commands.oidc import oidc

app = cyclopts.App()
app.command(db)
app.command(n8n)
app.command(oidc)


if __name__ == "__main__":
    app()

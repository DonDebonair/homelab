#!/usr/bin/env python

import cyclopts

from commands.db import db
from commands.oidc import oidc

app = cyclopts.App()
app.command(db)
app.command(oidc)


if __name__ == "__main__":
    app()

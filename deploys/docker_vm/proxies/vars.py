from deploys.docker_vm.proxies.secrets import (
    cloudflare_api_token,
    authelia_redis_password,
    authelia_smtp_password,
    authelia_smtp_username,
    authelia_jwt_secret,
    authelia_session_secret,
    authelia_storage_encryption,
    authelia_hmac_secret,
    authelia_jwks_private_pem,
    authelia_jwks_public_pem,
    authelia_ldap_username,
    authelia_ldap_password,
    authelia_db_password,
    cloudflare_tunnel_id,
    cloudflared_credentials_json,
)

caddy_version = "2.11.4"

smtp_server = "smtp.eu.mailgun.org"
smtp_port = 587

# cloudflared image's built-in nonroot user
CLOUDFLARE_UID = 65532
CLOUDFLARE_GID = 65532

oidc_clients = [
    {
        "id": "portainer",
        "name": "Portainer",
        "secret_hash": "$pbkdf2-sha512$310000$meniPHed3yo443IPRfpjcQ$XfnrR/A4Yc.u6yCdV2ihmZiNcZca3KL5LOxk6bgA53bGVvdlyqLQS0k30PP8.u1lUysHRzQtIDcNrUqcBZVNgg",
        "policy": "two_factor",
        "redirect_uris": ["https://docker.dv.zone"],
        "scopes": ["openid", "groups", "email", "profile"],
        "auth_method": "client_secret_basic",
    },
    {
        "id": "miniflux",
        "name": "Miniflux",
        "secret_hash": "$pbkdf2-sha512$310000$gUJaML/BKpb1ysabv0svWA$s6I7nX4PnlwTQOFy7xb0ovmux50nyuAAUrm3ZA0cYSnI91C5eWvvWjcb1aJHNJ3SuX1T5whw3JioI2F3eMf.PQ",
        "policy": "two_factor",
        "redirect_uris": ["https://rss.dv.zone/oauth2/oidc/callback"],
        "scopes": ["openid", "groups", "email", "profile"],
        "auth_method": "client_secret_post",
    },
    {
        "id": "pgadmin",
        "name": "pgAdmin",
        "secret_hash": "$pbkdf2-sha512$310000$6GViUVLeAZzSmpEjdnGm6Q$xDoTcWqqBb5simagRpDUmrjCN5ydaeW4Vz9Nktj..5ydKnB2ol.3SzmEkHU9RRotQwo4kRrRKTHrlFCqh61vQg",
        "policy": "two_factor",
        "redirect_uris": ["https://pgadmin.dv.zone/oauth2/authorize"],
        "scopes": ["openid", "email", "profile"],
        "auth_method": "client_secret_basic",
    },
    {
        "id": "grafana",
        "name": "Grafana",
        "secret_hash": "$pbkdf2-sha512$310000$ktHhV1vkILOMqcTAB8jB6A$Y8Mgy.IK4M7shKulcSMCNdKk3RRQZ0LIx1lAL6D0rhsPR/GRMt6jT5xh7zS2itjjw2WQ/4JHKtVuT5tb7h5TyA",
        "policy": "one_factor",
        "redirect_uris": ["https://grafana.dv.zone/login/generic_oauth"],
        "scopes": ["openid", "groups", "email", "profile"],
        "auth_method": "client_secret_basic",
        # Grafana reads `groups` from the ID token for role_attribute_path; Authelia
        # 4.39 drops it from the ID token unless a claims policy restores it.
        "claims_policy": "default",
    },
    {
        "id": "forgejo",
        "name": "Forgejo",
        "secret_hash": "$pbkdf2-sha512$310000$fbVkvKoKH2ntsklQpNeDMg$WGvHyZA0mpxqXBDPbdwDrMC75tU8tKUorF8GZ1PKRTYXr82.26mmYA.invgnbTs7kfisay8eMxWgotlRaH1tTA",
        "policy": "two_factor",
        "redirect_uris": ["https://git.dv.zone/user/oauth2/authelia/callback"],
        "scopes": ["openid", "groups", "email", "profile"],
        "auth_method": "client_secret_basic",
    },
    {
        "id": "paperless",
        "name": "paperless",
        "secret_hash": "$pbkdf2-sha512$310000$4iL9MIdWCyUDq8J8KLsNQg$hQgiA/wyQfFmPtR3OmuxiH9KHb7E5xEsanqinqqQYHlYIijKGzTPE..lw7x0NEZdURsOY050jreaDT3N40t5ow",
        "policy": "two_factor",
        "redirect_uris": ["https://docs.dv.zone/accounts/oidc/authelia/login/callback/"],
        "scopes": ["openid", "groups", "email", "profile"],
        "auth_method": "client_secret_basic",
        "require_pkce": True,
        "pkce_challenge_method": "S256",
    },
    {
        "id": "technitium-dns",
        "name": "Technitium DNS",
        "secret_hash": "$pbkdf2-sha512$310000$DNnvqm.hvRbHHMEy5Pvekg$XKdBrvs.aXC.S2HIoR3kIjr0Rrh.XYO4gX8LTpmxYaX3cB/3X9zf3TF1Dqz5fD/w108ApmQmDZ9A5SRbDUlSCA",
        "policy": "two_factor",
        "redirect_uris": [
            "https://dns1.dv.zone/sso/callback",
            "https://dns2.dv.zone/sso/callback",
        ],
        "scopes": ["openid", "groups", "email", "profile"],
        "auth_method": "client_secret_post",
        "require_pkce": True,
        "pkce_challenge_method": "S256",
    },
    {
        "id": "shelfmark",
        "name": "Shelfmark",
        "secret_hash": "$pbkdf2-sha512$310000$Mua8d671XktJKSVkjFFqjQ$LbUQprrlqe9uSVBxvT0ozVmVzbUvTh4nDnzKDGDTGBemhpto6aSJf1kQ1ts1z/fRcPe7WYLVoQFOE5Ga3fUTgw",
        "policy": "two_factor",
        "redirect_uris": ["https://shelfmark.dv.zone/api/auth/oidc/callback"],
        "scopes": ["openid", "groups", "email", "profile"],
        "auth_method": "client_secret_basic",
        "require_pkce": True,
        "pkce_challenge_method": "S256",
    },
    {
        "id": "outline",
        "name": "outline",
        "secret_hash": "$pbkdf2-sha512$310000$/L/3fq8VAiAkZMx5z/k/hw$dgEurJaC180NIZ0ljPVp90QCv0rXE8W/TVe2tSi2OKRXWgU7jc9h7rPOyvBfAik0k/UvvSVI1m84wtT5pB6s8A",
        "policy": "two_factor",
        "redirect_uris": ["https://outline.dv.zone/auth/oidc.callback"],
        "scopes": ["openid", "offline_access", "profile", "email"],
        "auth_method": "client_secret_post",
    },
    {
        "id": "affine",
        "name": "AFFiNE",
        "secret_hash": "$pbkdf2-sha512$310000$QCiF0JqzttY6B.C89/5f6w$C2/4eFn94FagKXh9z9GWqJdtd5H44dbA3JRVh6h6SfpD5P15Je/CyE7RanDJ3i.Us.UCPmOtNxCFclYv0PlM1w",
        "policy": "two_factor",
        "redirect_uris": ["https://affine.dv.zone/oauth/callback"],
        "scopes": ["openid", "profile", "email"],
        "auth_method": "client_secret_post",
    },
    {
        "id": "bookorbit",
        "name": "BookOrbit",
        "secret_hash": "$pbkdf2-sha512$310000$Tsk5h3BOqXUupTTmHINQCg$yAoK2jU4euvoby6GS8Qanw2f6WvP.JQONAB5kpGnojA6gs4lpNIS6Vg/6WNszTjCWtWM21m5lzgJZiXUfV8khQ",
        "policy": "two_factor",
        "redirect_uris": ["https://bookorbit.dv.zone/oauth2-callback"],
        "scopes": ["openid", "groups", "email", "profile"],
        "auth_method": "client_secret_post",
        "claims_policy": "default",
    },
]

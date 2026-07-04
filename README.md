# Homelab

This repository contains the configuration files and documentation for my homelab setup. It includes various services
and applications that I and my family rely on.

The homelab (or self-hosted environment) runs on a [Minisforum MS-A2](https://minisforumpc.eu/products/ms-a2-mini-pc) 
and a Synology DS1621+ NAS. Most services and applications run on the NAS. They should eventually be migrated to the 
Minisforum, in tandem with the migration from Ansible to pyinfra (see below).

2 versions of the homelab configuration are available, that are outlined below: the old Ansible setup and the new 
pyinfra setup. The goal is to migrate from Ansible to pyinfra, which is a more modern and efficient configuration 
management tool.

## Old: Ansible

**Main entrypoint**: `nas.yml`

**Relevant directories**:

- `roles/`: Ansible roles for different services and applications.
- `scripts/`: scripts for automating tasks around Ansible, such as generating DB users, OIDC clients, and more.

**Main commands**:

- `ansible-playbook nas.yml`: Run the Ansible playbook to configure the homelab. Optionally, you can specify a \
  particular tag to run only a subset of the playbook, e.g. `ansible-playbook -t docker-apps nas.yml` to only install 
  the Docker applications
- `ansible-vault encrypt_string -n <name> '<value>'`: Encrypt a secret value using Ansible Vault, which can then be 
   used in Ansible roles.

## New: Pyinfra

**Main entrypoint**: `deploy.py`

**Inventory**: `inventory.py`

**Relevant directories**:

- `deploys/`: pyinfra deploys for different services and applications.
- `facts/`: custom pyinfra facts for Proxmox and Synology.
- `operations/`: custom pyinfra operations for Proxmox and Synology.
- `models/`: models for custom pyinfra facts and operations.
- `op_secrets/`: custom string class for handling secrets in pyinfra with 1password.
- `group_data/`: data for pyinfra groups of hosts.
- `commands/`: CLI helpers (entrypoint `cmd.py`) for provisioning new PostgreSQL databases
  and OIDC clients — generating credentials, creating the 1Password items, and editing the
  relevant deploy config. See `commands/README.md`.

**Main commands**:

All pyinfra command should be run through `uv`.

- `uv run pyinfra inventory.py deploy.py -y`: Run the pyinfra deploy to configure the homelab. Optionally, you can 
  deploy only specific hosts or groups of hosts, e.g. `uv run pyinfra inventory.py deploy.py -y --limit postgres_lxc` 
  to only deploy the Postgres LXC.
  You can also specify a particular deploy to run, 
  e.g. `uv run pyinfra inventory.py deploys.docker_vm.users -y --limit docker_vm` to only run the users deploy for the 
  Docker VM.

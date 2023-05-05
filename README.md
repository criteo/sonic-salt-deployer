# SONiC Salt deployer

> This repository is part of [AFK](https://criteo.github.io/AFK).

The full documentation can be found here: [AFK documentation](https://criteo.github.io/AFK/SONiC-support/SONiC-Salt-Deployer/)

The goal of this program is to deploy and configure Salt minions on SONiC devices.

It includes:

* DNS server configuration
* Salt minion PEX
* Update grains script
* Systemd services / timers

Each part will be deployed only if necessary.

Once deployed, feel free to use our [SONiC Salt modules](https://github.com/criteo/sonic-saltstack/tree/main)!

# Prepare your environment

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements/base.txt
```

# How to use it

## Settings

See [settings.env](settings.env)

## Usage

```
pip install -r requirements/base.txt
python ./start.py
```

Or build the PEX via `tox -e bundle` and run the executable.

You can use this systemd [service](systemd/sonic-salt-deployer.service) and its [timer](systemd/sonic-salt-deployer.timer).

## How to contribute

see [CONTRIBUTING.md](CONTRIBUTING.md)

# Sonic Salt deployer

The goal of this program is to deploy and configure Salt minions on SONiC devices.

It includes:

* DNS server configuration
* Salt minion PEX
* Update grains script
* Systemd services / timers

Each part will be deployed only if necessary.

# Prepare your environment

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements/base.txt
```

# How to use it

TODO

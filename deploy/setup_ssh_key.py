#!/usr/bin/env python3
"""Upload SSH public key to new server using password auth via paramiko."""
import subprocess
import sys

# Install paramiko if needed
try:
    import paramiko
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
    import paramiko

HOST = "46.62.227.62"
USER = "root"
PASSWORD = "kXKHAXwspKjk"
PUBKEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOnKfvpOHWxZFHiCkWZdAJFb/BM/kyLXIJiljQgzsSib taxja-server"

print(f"Connecting to {HOST}...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASSWORD, timeout=15)

commands = [
    "mkdir -p ~/.ssh",
    f'echo "{PUBKEY}" >> ~/.ssh/authorized_keys',
    "chmod 700 ~/.ssh",
    "chmod 600 ~/.ssh/authorized_keys",
    "cat ~/.ssh/authorized_keys",
]

for cmd in commands:
    print(f"  Running: {cmd[:60]}...")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(f"    {out}")
    if err:
        print(f"    ERR: {err}")

client.close()
print("\nSSH key uploaded. Testing key-based auth...")

# Test key-based connection
client2 = paramiko.SSHClient()
client2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    pkey = paramiko.Ed25519Key.from_private_key_file(r"C:\Users\yk1e25\taxja-server-nopass")
    client2.connect(HOST, username=USER, pkey=pkey, timeout=15)
    stdin, stdout, stderr = client2.exec_command("echo 'SSH key auth works!'")
    print(stdout.read().decode().strip())
    client2.close()
    print("Done! Key-based SSH is working.")
except Exception as e:
    print(f"Key auth test failed: {e}")
    print("But the key was uploaded - try manually with:")
    print(f'  ssh -i C:\\Users\\yk1e25\\taxja-server-nopass root@{HOST}')

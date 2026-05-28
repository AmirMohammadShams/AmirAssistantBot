import paramiko
import sys

hostname = "62.60.212.224"
username = "root"
password = "pT2g97IEt9"

try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {hostname}...")
    client.connect(hostname, username=username, password=password, timeout=10)
    print("Connection successful!")
    
    stdin, stdout, stderr = client.exec_command("uname -a && pwd")
    print("Output:", stdout.read().decode())
    
    client.close()
except Exception as e:
    print(f"Connection failed: {e}")
    sys.exit(1)

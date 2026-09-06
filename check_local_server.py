import requests

try:
    r = requests.get('http://localhost:5000/auth/login', timeout=2)
    print("Local server status:", r.status_code)
except Exception as e:
    print("Local server is not running:", e)

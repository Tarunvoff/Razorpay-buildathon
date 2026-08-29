import sys

client_path = r"C:\Users\TARUN\AppData\Roaming\Python\Python313\site-packages\apiris\client.py"
with open(client_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Modify client.py to handle missing schema properly
if 'if not url.startswith(("http://", "https://")):' not in content:
    patch = """
        timing_ms = int((time.time() - started_at) * 1000)

        # Fix: If it's a client error before network (like MissingSchema), set timing to None
        if error and error.get("name") in ["MissingSchema", "InvalidURL", "InvalidSchema"]:
            timing_ms = None
"""
    content = content.replace("timing_ms = int((time.time() - started_at) * 1000)", patch)
    
    with open(client_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Patched client.py")
else:
    print("Already patched")

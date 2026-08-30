import sys
import re

cli_path = r"C:\Users\TARUN\AppData\Roaming\Python\Python313\site-packages\apiris\cli.py"

with open(cli_path, 'r', encoding='utf-8') as f:
    text = f.read()

bad_text = '''        if response.status_code is None:
            console.print("[bold yellow]Note:[/bold yellow] Fast edge-level rejection (No network call)")
'''
text = text.replace(bad_text, '')

# Now let's inject it correctly where we wanted it!
target = 'console.print(f"[bold]Status Code:[/bold] {response.status_code}")'
replacement = target + '\n            if str(response.status_code) == "None":\n                console.print("[bold yellow]Note:[/bold yellow] Fast edge-level rejection (No network call)")'

if 'Fast edge-level rejection' not in text:
    text = text.replace(target, replacement)

with open(cli_path, 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed cli.py!')

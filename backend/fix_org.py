import os
import glob

files = glob.glob('app/tools/*.py')
replacement = '''from app.core.context import org_id_var
    ORG_ID = org_id_var.get()'''

for f in files:
    with open(f, 'r') as file:
        content = file.read()
    
    if 'ORG_ID = "org_demo_001"' in content:
        content = content.replace('ORG_ID = "org_demo_001"', replacement)
        with open(f, 'w') as file:
            file.write(content)
        print(f"Updated {f}")

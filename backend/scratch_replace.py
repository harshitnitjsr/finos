import pathlib
p = pathlib.Path('d:/finos/backend/app/core/seed.py')
text = p.read_text('utf-8')
text = text.replace('"org_demo_001"', '"cc95cadf-ba95-474f-929e-b77f8b0b934c"')
p.write_text(text, 'utf-8')

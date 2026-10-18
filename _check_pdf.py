import pdfplumber

with pdfplumber.open('samples/onko.pdf') as pdf:
    for i, page in enumerate(pdf.pages):
        print(f'=== PAGE {i} ===')
        text = page.extract_text() or '(пусто)'
        print(text)
        print()
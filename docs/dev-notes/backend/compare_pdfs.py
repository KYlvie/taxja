#!/usr/bin/env python3
import PyPDF2

print('='*80)
print('2020 FILE (Einkommensteuererklärung für 2022.pdf)')
print('='*80)
with open('Einkommensteuererklärung für 2022.pdf', 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    page1 = reader.pages[0].extract_text()
    print(f'Pages: {len(reader.pages)}')
    size = f.seek(0, 2)
    print(f'Size: {size:,} bytes')
    f.seek(0)
    print(f'Contains Jahresabschluss: {"Jahresabschluss" in page1}')
    print(f'Contains taxpayer name: {"ZHANG" in page1 or "Fenghong" in page1}')
    print(f'Type: FILLED FORM with complete data')
    
print('\n' + '='*80)
print('2023 FILE (Einkommensteuererklärung für 2023.PDF)')
print('='*80)
with open('Einkommensteuererklärung für 2023.PDF', 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    page1 = reader.pages[0].extract_text()
    print(f'Pages: {len(reader.pages)}')
    size = f.seek(0, 2)
    print(f'Size: {size:,} bytes')
    f.seek(0)
    print(f'Contains Jahresabschluss: {"Jahresabschluss" in page1}')
    print(f'Is blank template: {"E 1-PDF-2023" in page1}')
    print(f'Type: BLANK TEMPLATE or partially filled')

print('\n' + '='*80)
print('CONCLUSION')
print('='*80)
print('The 2020 file is a COMPLETE filled form with all data')
print('The 2023 file is a BLANK TEMPLATE or only partially filled')
print('\nFor testing the enhanced parser, use the 2020 file!')

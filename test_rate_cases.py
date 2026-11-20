import sys
sys.path.insert(0, 'Backend-kirana-billing')
from services.regex_parser import parse_bill_with_regex

cases = [
    'साखर एक किलो साठ रुपये',
    'साखर 1 किलो 60 रुपये',
    'साखर एक किलो साठ',
    'साखर 1 किलो 60',
    'साखर 1 किलो साठ',
    'साखर एक किलो 60 रुपये',
    'साखर 60 रुपये 1 किलो',
    'साखर 60 रुपये',
    'साखर साठ रुपये',
    'साखर साठ',
    'साखर 60',
    '1 किलो साखर 60 रुपये',
    'एक किलो साखर साठ रुपये',
    'एक किलो साखर 60',
    'एक किलो साखर साठ',
    'रवा एक किलो पन्नास रुपये',
    'रवा 1 किलो 50 रुपये',
    'रवा 1 किलो पन्नास',
    'रवा 1 किलो 50',
    'रवा 50 रुपये',
    'रवा पन्नास रुपये',
    'रवा पन्नास',
    'रवा 50',
    '1 किलो रवा 50 रुपये',
    'एक किलो रवा पन्नास रुपये',
    'एक किलो रवा 50',
    'एक किलो रवा पन्नास',
    'साखर 1 किलो 60 साठ रुपये',
    'रवा 1 किलो 50 पन्नास रुपये',
    'Sakhar 1kilo 60 saath rupaye',
    '1kg 1kilo rawa 50rs Pannas rupaye',
    'sakhar 1kilo 60',
    'rawa 1kilo 50',
    'sakhar ek kilo 60 rs',
    'rawa ek kilo 50 rs',
    'sakhar 1 kilo saath rs',
    'rawa 1 kilo pannas rs',
    'sakhar ek kilo saath',
    'rawa ek kilo pannas',
    'sakhar 1 kilo bhaw 60',
    'sakhar 1 kg rate 60',
    'rawa 1 kg darr 50',
    'sakhar 1 kilo rate 60 rs',
    'sakhar 60 rupaye kilo',
    'rawa 50 rupaye kilo',
    'sakhar 60 rs kilo',
    'rawa 50 rs kilo',
    '2 kilo sakhar 60 rupaye kilo',
    '2 kilo sakhar 60 rs darr',
    'साखर साठ भावाने दोन किलो',
    'दोन किलो साखर साठ भावाने',
    'साखर ६० भाव १ किलो',
    'साखर ६० दर १ किलो',
    'साखर ६० रुपयाने २ किलो',
    'साखर २ किलो ६० रुपये किलोने',
    'साखर ६० रुपये किलो २ किलो',
    'दोन किलो साखर ६० रुपये किलो',
    'साखर ६० रुपये किलो',
    'साबण ५ नग ५०',
    'कोलगेट २ नग १२०',
    'Sakhar 1kilo 60 saath rupaye rawa 1kilo 50 rs pannas rupaye',
    'साखर २ किलो ६० रुपये किलोने आणि रवा १ किलो पन्नास रुपये',
]

failures = []
for c in cases:
    res = parse_bill_with_regex(c, {'outputLang': 'mr'})
    if not res:
        failures.append((c, 'NO ITEMS FOUND'))
    else:
        for it in res:
            name = it['name']
            price = it['price']
            qty = it['quantity']
            unit = it['unit']
            amount = it.get('amount', 0)
            if price <= 0:
                failures.append((c, f'ZERO PRICE: {it}'))
            else:
                print(f'OK: {c} -> {name} {qty}{unit} @ Rs.{price} (tot: {amount})')

print(f'\n--- TOTAL FAILURES: {len(failures)} ---')
for f in failures:
    print('FAILED:', f[0], '->', f[1])

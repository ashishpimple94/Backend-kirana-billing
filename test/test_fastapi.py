"""
test_fastapi.py
Unit tests for Python FastAPI Kirana billing engine.
"""

import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.marathi_normalizer import (
    number_to_marathi_words,
    convert_bill_line_to_speech,
)
from services.regex_parser import parse_bill_with_regex

print("==================================================")
print("1. Testing Number-to-Speech Converter (30 Reference Items)")
print("==================================================")

ref_table = [
    (780, "satshey aainshi"),
    (990, "naushey navvad"),
    (180, "ekshey aainshi"),
    (560, "pachshey saath"),
    (230, "donshey tees"),
    (788, "satshey atthyaainshi"),
    (1000, "ek hazaar"),
    (2890, "don hazaar aathshey navvad"),
    (553, "pachshey trepanna"),
    (10000, "daha hazaar"),
    (455, "chaarshey panchaavanna"),
    (710, "satshey daha"),
    (810, "aathshey daha"),
    (910, "naushey daha"),
    (310, "teenshey daha"),
    (210, "donshey daha"),
    (120, "ekshey vees"),
    (130, "ekshey tees"),
    (140, "ekshey chalis"),
    (160, "ekshey saath"),
    (260, "donshey saath"),
    (460, "chaarshey saath"),
    (660, "sahashey saath"),
    (770, "satshey sattar"),
    (380, "teenshey aainshi"),
    (280, "donshey aainshi"),
    (450, "chaarshey pannas"),
    (700, "satshey"),
    (1140, "ek hazaar ekshey chalis"),
    (1200, "ek hazaar donshey"),
]

passed_ref = 0
for amount, expected in ref_table:
    got = number_to_marathi_words(amount)
    if got == expected:
        passed_ref += 1
    else:
        print(f"❌ FAIL: {amount} => Got: '{got}' | Expected: '{expected}'")

print(f"✅ Reference Table Passed: {passed_ref} / {len(ref_table)}\n")

print("==================================================")
print("2. Testing Spoken Pronunciation Echoes")
print("==================================================")

echo_tests = [
    ("sakhar 1kg 60 sath", 60.0, "sath"),
    ("sugar 1kg 60 sixty", 60.0, "sixty"),
    ("masoor 1kg 95 panchyannav", 95.0, "panchyannav"),
    ("shengdane 1kg 160 one sixty", 160.0, "one sixty"),
    ("besan 1kg 130 ekshe tees", 130.0, "ekshe tees"),
    ("celery 1kg 50 pachaas", 50.0, "pachaas"),
]

passed_echoes = 0
for test_str, exp_price, exp_pronounce in echo_tests:
    items = parse_bill_with_regex(test_str)
    if items and items[0]["price"] == exp_price:
        passed_echoes += 1
        print(f"✅ PASSED: '{test_str}' -> Name: '{items[0]['name']}', Price: ₹{items[0]['price']}, Pronounce: '{items[0].get('spoken_pronunciation')}'")
    else:
        print(f"❌ FAILED: '{test_str}' -> Items: {items}")

print(f"✅ Echo Tests Passed: {passed_echoes} / {len(echo_tests)}\n")

print("==================================================")
print("3. Testing MRP Line Conversion")
print("==================================================")

mrp_line = "Patanjali biscuit box 10/- 710"
speech = convert_bill_line_to_speech(mrp_line)
exp_speech = "Patanjali biscuit box 10/- satshey daha rupaye 710"
if speech == exp_speech:
    print(f"✅ PASSED: '{mrp_line}' => '{speech}'")
else:
    print(f"❌ FAILED: Got: '{speech}' | Expected: '{exp_speech}'")

print("\n==================================================")
print("4. Testing All Kirana Prices (120, 130, 140, 160, 260, 460, 660, 560, 770, 380, 280, 450, 700, 230, 1140, 1200)")
print("==================================================")

price_tests = [
    ("Sakhar 120", 120.0),
    ("Besan 130", 130.0),
    ("Maida 140", 140.0),
    ("Shengdane 160", 160.0),
    ("Moong Dal 260", 260.0),
    ("Gahu 460", 460.0),
    ("Tandul 560", 560.0),
    ("Tel 660", 660.0),
    ("Kaju 770", 770.0),
    ("Badam 380", 380.0),
    ("Poha 280", 280.0),
    ("Mirchi 450", 450.0),
    ("Jeera 700", 700.0),
    ("Chai 230", 230.0),
    ("Doodh 1140", 1140.0),
    ("Ghee 1200", 1200.0),
]

passed_prices = 0
for test_str, exp_price in price_tests:
    items = parse_bill_with_regex(test_str)
    if items and items[0]["price"] == exp_price:
        passed_prices += 1
    else:
        print(f"❌ FAILED: '{test_str}' -> Items: {items}")

print(f"✅ Price Tests Passed: {passed_prices} / {len(price_tests)}\n")

print("==================================================")
print("5. Hallucination Guard Test (100000)")
print("==================================================")
halluc_items = parse_bill_with_regex("Sakhar 100000")
if not halluc_items or halluc_items[0]["price"] < 15000:
    print(f"✅ PASSED: 100000 hallucination successfully rejected! (Items: {halluc_items})")
else:
    print(f"❌ FAILED: 100000 was accepted: {halluc_items}")

print("==================================================")

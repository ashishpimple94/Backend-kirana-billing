const { parseBillWithRegex } = require('../services/regexParser');
const { normalizeMarathiTranscript } = require('../services/marathiNormalizer');

console.log('--- RUNNING NLP & SPEECH TEST SUITE ---');

let failed = 0;

// 1. Accents Test
const accentPhrases = [
  ['ekshe pastis rupaye', '135 rs'],
  ['एकशे पस्तीस रुपये', '135 rs'],
  ['ek se pastis rupaye', '135 rs'],
  ['ekshe chalis rupaye', '140 rs'],
  ['एकशे चाळीस रुपये', '140 rs'],
  ['ekshe navvad rupaye', '190 rs'],
  ['एकशे नव्वद रुपये', '190 rs'],
  ['sade pacahshe rupaye', '550 rs'],
  ['पाचशे पन्नास रुपये', '550 rs'],
  ['pachshe pannas rupaye', '550 rs'],
  ['pachse pannas rupaye', '550 rs'],
  ['naushe ayshi rupaye', '980 rs'],
  ['navshe aishi rupaye', '980 rs'],
  ['नऊशे ऐंशी रुपये', '980 rs'],
  ['don hajar donshe vees rupaye', '2220 rs'],
  ['दोन हजार दोनशे वीस रुपये', '2220 rs'],
  ['don hajar donshe tees rupaye', '2230 rs'],
  ['दोन हजार दोनशे तीस रुपये', '2230 rs'],
  ['pach hajar rupaye', '5000 rs'],
  ['पाच हजार रुपये', '5000 rs'],
  ['paach hajar rupaye', '5000 rs'],
  ['panch hazar rupaye', '5000 rs'],
  ['5 hajar rupaye', '5000 rs'],
  ['daha hajar rupaye', '10000 rs'],
  ['दहा हजार रुपये', '10000 rs']
];

let accPass = 0;
for (const [input, expected] of accentPhrases) {
  const norm = normalizeMarathiTranscript(input);
  if (norm === expected) {
    accPass++;
  } else {
    failed++;
    console.error(`FAIL Accent: "${input}" -> got "${norm}", expected "${expected}"`);
  }
}
console.log(`✓ Accents Test: ${accPass}/${accentPhrases.length} Passed`);

// 2. Kirana Orders Test
const orders = [
  { input: "एक किलो सरगम पत्ती चहा ५५० साडेपाचशे रुपये", expected: { name: 'सरगम पत्ती चहा', qty: 1, unit: 'kg', price: 550 } },
  { input: "पाव किलो २५० ग्रॅम सुपर डस्ट ७० सत्तर रुपये", expected: { name: 'सुपर डस्ट चहा', qty: 250, unit: 'gm', amount: 70 } },
  { input: "एक किलो साखर साठ रुपये", expected: { name: 'साखर', qty: 1, unit: 'kg', price: 60 } },
  { input: "दोन किलो शेंगदाणे एकशे चाळीस रुपये", expected: { name: 'शेंगदाणे', qty: 2, unit: 'kg', price: 140 } },
  { input: "एक किलो काजू एकशे पस्तीस रुपये", expected: { name: 'काजू', qty: 1, unit: 'kg', price: 135 } },
  { input: "एक किलो बदाम एकशे नव्वद रुपये", expected: { name: 'बदाम', qty: 1, unit: 'kg', price: 190 } },
  { input: "एक किलो चारोळी नऊशे ऐंशी रुपये", expected: { name: 'चारोळी', qty: 1, unit: 'kg', price: 980 } },
  { input: "दोन बॉक्स साबण पाच हजार रुपये", expected: { name: 'साबण', qty: 2, unit: 'box', price: 5000 } },
  { input: "एक डबा तेल दोन हजार दोनशे वीस रुपये", expected: { name: 'गोडेतेल', qty: 1, unit: 'box', price: 2220 } },
  { input: "एक डबा तूप दोन हजार दोनशे तीस रुपये", expected: { name: 'तूप', qty: 1, unit: 'box', price: 2230 } }
];

let orderPass = 0;
for (const ord of orders) {
  const parsed = parseBillWithRegex(ord.input, { priceMode: 'per_unit', language: 'mr-IN' });
  if (parsed.length > 0) {
    const itm = parsed[0];
    const nameOk = itm.name === ord.expected.name;
    const qtyOk = itm.quantity === ord.expected.qty;
    const unitOk = itm.unit === ord.expected.unit;
    const priceOk = ord.expected.amount ? itm.amount === ord.expected.amount : itm.price === ord.expected.price;
    if (nameOk && qtyOk && unitOk && priceOk) {
      orderPass++;
    } else {
      failed++;
      console.error(`FAIL Order: "${ord.input}" ->`, itm, 'expected:', ord.expected);
    }
  } else {
    failed++;
    console.error(`FAIL Order: "${ord.input}" -> No items extracted!`);
  }
}
console.log(`✓ Orders Test: ${orderPass}/${orders.length} Passed`);

// 3. English Output Mode
const englishOrders = [
  "1 kg sakhar 60 rs",
  "2 kg shengdane 140 rs",
  "1 kg rawa 55 rs",
  "1 kg maida 45 rs",
  "1 kg sargam dust tea 550 rs",
  "250 gm super dust 70 rs",
  "1 kg charoli 980 rs",
  "2 box saban 5000 rs"
];

let engPass = 0;
for (const eo of englishOrders) {
  const parsed = parseBillWithRegex(eo, { priceMode: 'per_unit', language: 'mr-IN', outputLang: 'en' });
  if (parsed.length > 0 && parsed[0].name) {
    engPass++;
  } else {
    failed++;
    console.error(`FAIL English Order: "${eo}"`);
  }
}
console.log(`✓ English Mode Test: ${engPass}/${englishOrders.length} Passed`);

// 4. Direct Spoken & Brand Preservation Tests
const brandAndNoCurrencyOrders = [
  { input: "२ किलो साखर ४० , १ किलो मैदा २५", expectedCount: 2 },
  { input: "५०० ग्रॅम चहा ११० , १ लिटर गोडेतेल १६०", expectedCount: 2 },
  { input: "२ किलो फॉर्च्यून तेल १६० रुपये", expectedCount: 1, expectedName: "फॉर्च्यून तेल" },
  { input: "१ पॅकेट वाघ बकरी चहा ११० रुपये", expectedCount: 1, expectedName: "वाघ बकरी चहा" },
  { input: "२ बॉक्स गोदरेज साबण ५००० रुपये", expectedCount: 1, expectedName: "गोदरेज साबण" },
  { input: "साखर २ किलो चाळीस", expectedCount: 1, expectedPrice: 40 },
  { input: "५०० ग्रॅम हळदीराम भुजिया १८० रुपये", expectedCount: 1, expectedName: "हळदीराम भुजिया" },
  { input: "१ तोळा विलायची ४० रुपये", expectedCount: 1, expectedName: "वेलची" },
  { input: "10 packet balaji wafers 50 rupaye", expectedCount: 1, expectedName: "Balaji Wafers" },
  { input: "Super dust 250gm 70 rupaye", expectedCount: 1, expectedName: "सुपर डस्ट चहा" },
  { input: "1kg Besan 120 rupaye", expectedCount: 1, expectedName: "बेसन" },
  { input: "1 kg tel 380 rupaye", expectedCount: 1, expectedPrice: 380 },
  { input: "1 kg badam 700 rupaye", expectedCount: 1, expectedPrice: 700 },
  { input: "1 kg kaju 1140 rupaye", expectedCount: 1, expectedPrice: 1140 },
  { input: "1 box ghee 1200 rupaye", expectedCount: 1, expectedPrice: 1200 }
];

let brandPass = 0;
for (const b of brandAndNoCurrencyOrders) {
  const parsed = parseBillWithRegex(b.input, { priceMode: 'per_unit', language: 'mr-IN' });
  if (parsed.length === b.expectedCount) {
    if (b.expectedName && parsed[0].name !== b.expectedName) {
      failed++;
      console.error(`FAIL Brand Name: "${b.input}" -> got "${parsed[0].name}", expected "${b.expectedName}"`);
    } else if (b.expectedPrice && parsed[0].price !== b.expectedPrice) {
      failed++;
      console.error(`FAIL Price: "${b.input}" -> got "${parsed[0].price}", expected "${b.expectedPrice}"`);
    } else {
      brandPass++;
    }
  } else {
    failed++;
    console.error(`FAIL Count: "${b.input}" -> got ${parsed.length} items, expected ${b.expectedCount}`);
  }
}
console.log(`✓ Direct Spoken & Brands Test: ${brandPass}/${brandAndNoCurrencyOrders.length} Passed`);

const totalTests = accentPhrases.length + orders.length + englishOrders.length + brandAndNoCurrencyOrders.length;

if (failed > 0) {
  console.error(`\n❌ TEST SUITE FAILED with ${failed} errors.`);
  process.exit(1);
} else {
  console.log(`\n✅ ALL ${totalTests} TESTS PASSED SUCCESSFULLY!`);
  process.exit(0);
}

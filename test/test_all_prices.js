const {
  numberToMarathiWords,
  convertBillLineToMarathiSpeech,
  parseMarathiSpokenNumbers,
} = require('../services/marathiNormalizer');
const { parseBillWithRegex } = require('../services/regexParser');

console.log('--- 1. Testing Number-To-Speech Converter (Reference Table) ---');
const refTable = [
  [780, 'satshey aainshi'],
  [990, 'naushey navvad'],
  [180, 'ekshey aainshi'],
  [560, 'pachshey saath'],
  [230, 'donshey tees'],
  [788, 'satshey atthyaainshi'],
  [1000, 'ek hazaar'],
  [2890, 'don hazaar aathshey navvad'],
  [553, 'pachshey trepanna'],
  [10000, 'daha hazaar'],
  [455, 'chaarshey panchaavanna'],
  [710, 'satshey daha'],
  [810, 'aathshey daha'],
  [910, 'naushey daha'],
  [310, 'teenshey daha'],
  [210, 'donshey daha'],
  [120, 'ekshey vees'],
  [130, 'ekshey tees'],
  [140, 'ekshey chalis'],
  [160, 'ekshey saath'],
  [260, 'donshey saath'],
  [460, 'chaarshey saath'],
  [660, 'sahashey saath'],
  [770, 'satshey sattar'],
  [380, 'teenshey aainshi'],
  [280, 'donshey aainshi'],
  [450, 'chaarshey pannas'],
  [700, 'satshey'],
  [1140, 'ek hazaar ekshey chalis'],
  [1200, 'ek hazaar donshey'],
];

let refPassed = 0;
for (const [amount, expected] of refTable) {
  const words = numberToMarathiWords(amount);
  const ok = words === expected;
  if (ok) refPassed++;
  else console.log(`FAIL: ${amount} => got "${words}", expected "${expected}"`);
}
console.log(`Reference Table Passed: ${refPassed} / ${refTable.length}`);

console.log('\n--- 2. Testing MRP Lines Conversion ---');
const mrpLines = [
  'Patanjali biscuit box 10/- 710',
  'Sakhar 10/- 120',
  'Besan 10/- 130',
  'Maida 10/- 140',
  'Shengdane 10/- 160',
  'Moong Dal 10/- 260',
  'Gahu 10/- 460',
  'Tandul 10/- 560',
  'Tel 10/- 660',
  'Kaju 10/- 770',
  'Badam 10/- 380',
  'Poha 10/- 280',
  'Mirchi 10/- 450',
  'Jeera 10/- 700',
  'Chai 10/- 230',
  'Doodh 10/- 1140',
  'Ghee 10/- 1200',
];

mrpLines.forEach((line) => {
  console.log(line, '===>', convertBillLineToMarathiSpeech(line));
});

console.log('\n--- 3. Testing Price Parsing Across Pronunciations (1 to 5000) ---');
const spokenTests = [
  // 120
  'Sakhar 1kg 120', 'Sakhar 1kg ekshe vees', 'Sakhar 1kg ekshey vees', 'Sakhar 1kg ek sau bees', 'Sakhar 1kg one twenty', 'Sakhar 120',
  // 130
  'Besan 1kg 130', 'Besan 1kg ekshe tees', 'Besan 1kg ek sau tees', 'Besan 1kg one thirty', 'Besan 130',
  // 140
  'Maida 1kg 140', 'Maida 1kg ekshe chalis', 'Maida 1kg one forty', 'Maida 140',
  // 160
  'Shengdane 1kg 160', 'Shengdane 1kg ekshe saath', 'Shengdane 1kg one sixty', 'Shengdane 160',
  // 260
  'Moong Dal 1kg 260', 'Moong Dal 1kg donshey saath', 'Moong Dal 1kg two sixty', 'Moong Dal 260',
  // 460
  'Gahu 10kg 460', 'Gahu 10kg chaarshey saath', 'Gahu 10kg four sixty', 'Gahu 460',
  // 560
  'Tandul 5kg 560', 'Tandul 5kg pachshey saath', 'Tandul 5kg five sixty', 'Tandul 560',
  // 660
  'Tel 1 litre 660', 'Tel 1 litre sahashey saath', 'Tel 1 litre six sixty', 'Tel 660',
  // 770
  'Kaju 250gm 770', 'Kaju 250gm satshey sattar', 'Kaju 250gm seven seventy', 'Kaju 770',
  // 380
  'Badam 250gm 380', 'Badam 250gm teenshey aainshi', 'Badam 250gm three eighty', 'Badam 380',
  // 280
  'Poha 1kg 280', 'Poha 1kg donshey aainshi', 'Poha 1kg two eighty', 'Poha 280',
  // 450
  'Mirchi 1kg 450', 'Mirchi 1kg chaarshey pannas', 'Mirchi 1kg four fifty', 'Mirchi 450',
  // 700
  'Jeera 250gm 700', 'Jeera 250gm satshey', 'Jeera 250gm seven hundred', 'Jeera 700',
  // 230
  'Chai 1kg 230', 'Chai 1kg donshey tees', 'Chai 1kg two thirty', 'Chai 230',
  // 1140
  'Doodh 1 litre 1140', 'Doodh 1 litre akrashe chalis', 'Doodh 1 litre eleven forty', 'Doodh 1140',
  // 1200
  'Ghee 1kg 1200', 'Ghee 1kg barashe', 'Ghee 1kg twelve hundred', 'Ghee 1200',
  // 2500
  'Kaju 1kg 2500', 'Kaju 1kg adeech hazaar', 'Kaju 1kg two thousand five hundred',
  // 5000
  'Dryfruits 5000', 'Dryfruits pach hazaar', 'Dryfruits five thousand',
  // Lakh sanity check (must NOT hallucinate 100000)
  'Lux saban 5 piece', 'Sakhar 1kg laav', 'Chaha 1 packet laagte',
];

let parsePassed = 0;
for (const test of spokenTests) {
  const items = parseBillWithRegex(test);
  if (items.length > 0) {
    parsePassed++;
  } else {
    console.log(`PARSE FAIL: "${test}" => 0 items parsed`);
  }
}
console.log(`\nSpoken Parsing Passed: ${parsePassed} / ${spokenTests.length}`);

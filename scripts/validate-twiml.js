#!/usr/bin/env node
/**
 * validate-twiml.js — Validate TwiML XML structure.
 * Usage: node scripts/validate-twiml.js [file.xml]
 *        echo '<Response><Say>Hi</Say></Response>' | node scripts/validate-twiml.js
 */
const fs = require('fs');

function validateTwiml(xml) {
  const errors = [];
  if (!xml.includes('<Response>')) errors.push('Missing <Response> root');
  if (!xml.includes('</Response>')) errors.push('Missing </Response> closing tag');
  const openSay = (xml.match(/<Say/g) || []).length;
  const closeSay = (xml.match(/<\/Say>/g) || []).length;
  if (openSay !== closeSay) errors.push(`<Say> mismatch: ${openSay} open, ${closeSay} close`);
  const openGather = (xml.match(/<Gather/g) || []).length;
  const closeGather = (xml.match(/<\/Gather>/g) || []).length;
  if (openGather !== closeGather) errors.push(`<Gather> mismatch: ${openGather} open, ${closeGather} close`);
  return errors;
}

const input = process.argv[2]
  ? fs.readFileSync(process.argv[2], 'utf8')
  : (process.stdin.isTTY ? '' : fs.readFileSync(0, 'utf8'));

if (!input.trim()) {
  console.error('Usage: node validate-twiml.js <file.xml>');
  console.error('   or: echo "<Response>...</Response>" | node validate-twiml.js');
  process.exit(1);
}

const errors = validateTwiml(input);
if (errors.length) {
  console.error('TwiML validation failed:');
  errors.forEach((e) => console.error('  -', e));
  process.exit(1);
}
console.log('TwiML structure OK');

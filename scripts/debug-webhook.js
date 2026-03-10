#!/usr/bin/env node
/**
 * debug-webhook.js — Simulate a Twilio webhook request for local testing.
 * Usage: node scripts/debug-webhook.js [step]
 * Requires: TWILIO_WEBHOOK_BASE_URL, TWILIO_AUTH_TOKEN (optional for validation)
 */
const step = process.argv[2] || 'start';
const baseUrl = process.env.TWILIO_WEBHOOK_BASE_URL || 'https://twilio.kozytherocket.space/lb-automotive/api/twilio/webhook';
const url = `${baseUrl}?step=${step}`;

const params = {
  CallSid: 'CA' + Math.random().toString(36).slice(2, 15),
  From: '+15551234567',
  Digits: null,
  SpeechResult: null,
};

console.log('Debug webhook request:');
console.log('  URL:', url);
console.log('  Params:', JSON.stringify(params, null, 2));
console.log('\nTo test with curl:');
console.log(`  curl -X POST "${url}" -d "CallSid=${params.CallSid}" -d "From=${params.From}"`);
console.log('\nAdd -d "Digits=1" or -d "SpeechResult=appointment" for user input.');

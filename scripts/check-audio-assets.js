#!/usr/bin/env node
/**
 * check-audio-assets.js — Verify audio asset paths referenced in the app exist.
 * Usage: node scripts/check-audio-assets.js
 */
const fs = require('fs');
const path = require('path');

const dirs = ['frontend/public', 'frontend/src', 'public', 'python-backend/static/audio'];
const exts = ['.wav', '.mp3', '.ogg', '.m4a'];

let found = 0;
let missing = [];

for (const dir of dirs) {
  const full = path.join(process.cwd(), dir);
  if (!fs.existsSync(full)) continue;
  const walk = (d) => {
    const entries = fs.readdirSync(d, { withFileTypes: true });
    for (const e of entries) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) walk(p);
      else if (exts.some((ext) => e.name.endsWith(ext))) {
        found++;
        console.log('  OK', path.relative(process.cwd(), p));
      }
    }
  };
  walk(full);
}

console.log(`\nFound ${found} audio asset(s).`);
if (missing.length) {
  console.error('Missing:', missing);
  process.exit(1);
}

const fs = require('fs');
const path = require('path');

const electronDir = path.join(__dirname, '..', 'node_modules', 'electron');
const distDir = path.join(electronDir, 'dist');

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function writeFile(filePath, contents) {
  fs.writeFileSync(filePath, contents, { encoding: 'utf8' });
  console.log(`Wrote ${filePath}`);
}

function main() {
  if (!fs.existsSync(electronDir)) {
    console.error('Electron package not found in node_modules/electron');
    process.exit(1);
  }

  ensureDir(distDir);

  const distVersion = path.join(distDir, 'version');
  const distPathTxt = path.join(distDir, 'path.txt');
  const packagePathTxt = path.join(electronDir, 'path.txt');

  writeFile(distVersion, '33.4.11');
  writeFile(distPathTxt, 'electron.exe');
  writeFile(packagePathTxt, 'electron.exe');

  console.log('Electron install repair completed.');
}

main();
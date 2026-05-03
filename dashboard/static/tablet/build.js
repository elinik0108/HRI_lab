#!/usr/bin/env node
/**
 * build.js — Compile Pepper tablet pages for the robot's old embedded browser
 * ============================================================================
 * Pepper's tablet runs an early Chromium build (~v38, circa 2014) which only
 * supports ES5 JavaScript and has no CSS custom properties, clamp(), fetch(),
 * or URLSearchParams.
 *
 * This script:
 *   1. Transpiles ES6+ syntax → ES5 via Babel  (const, arrow fns, template
 *      literals, destructuring, for-of, shorthand props, …)
 *   2. Inlines CSS custom properties (var(--xxx)) with hard-coded values.
 *   3. Replaces CSS clamp() with the max value (safe for 1280 px tablet).
 *   4. Expands the CSS inset shorthand.
 *   5. Bundles two tiny polyfills (fetch + URLSearchParams) into polyfills.js
 *      and injects them at the top of every HTML page.
 *
 * Output: ./dist/  (gitignored — regenerated each time)
 *
 * Usage:
 *   npm install        (first time only)
 *   node build.js      (or: npm run build)
 */
'use strict';

const fs   = require('fs');
const path = require('path');

// ── Sanity: Babel must be installed ─────────────────────────────────────────
let babel;
try {
  babel = require('@babel/core');
} catch (_) {
  console.error('[build] ERROR: @babel/core not found. Run: npm install');
  process.exit(1);
}

const SRC_DIR  = __dirname;
const DIST_DIR = path.join(__dirname, 'dist');

// Files/directories to skip when scanning the source directory
const SKIP = new Set([
  'build.js', 'package.json', 'package-lock.json', 'node_modules', 'dist',
]);

// ── Babel: target IE 11 to guarantee full ES5 output ────────────────────────
const BABEL_CONFIG = {
  presets: [[
    '@babel/preset-env',
    {
      // IE 11 is ES5-only; this forces all ES6+ syntax to be transpiled.
      targets: { ie: '11' },
      modules: false,   // don't wrap in require/define — these are IIFE browser scripts
    },
  ]],
  compact: false,
  retainLines: false,
};

// ── CSS: hard-coded values for each CSS custom property ─────────────────────
// Source of truth: base.css :root block.
// Font-size clamp() is pre-resolved to its maximum (right for Pepper 1280 px).
const CSS_VARS = {
  '--bg':         '#0d1117',
  '--surface':    '#161b22',
  '--border':     '#30363d',
  '--accent':     '#58a6ff',
  '--accent-dk':  '#1f6feb',
  '--text':       '#e6edf3',
  '--text-muted': '#8b949e',
  '--success':    '#3fb950',
  '--warning':    '#d29922',
  '--danger':     '#f85149',
  '--radius':     '1rem',
  '--radius-lg':  '1.5rem',
  // clamp(2rem, 6vw, 4.5rem)    @ 1280px → 6vw ≈ 4.8rem > max → 4.5rem
  '--title-size': '2rem',
  // clamp(1.4rem, 3vw, 2.2rem)  → 2.2rem
  '--body-size':  '2.2rem',
  // clamp(1rem, 2vw, 1.5rem)    → 1.5rem
  '--small-size': '1.5rem',
  // clamp(1.2rem, 3vw, 2rem)    → 2rem
  '--btn-size':   '2rem',
};


/**
 * Recursively copy a directory tree from `src` to `dest`.
 * Used for static assets (images, fonts, etc.) that don't need transformation.
 */
function copyDir(src, dest) {
  if (!fs.existsSync(src)) return;
  if (!fs.existsSync(dest)) fs.mkdirSync(dest, { recursive: true });

  var entries = fs.readdirSync(src);
  for (var i = 0; i < entries.length; i++) {
    var entry = entries[i];
    var srcPath  = path.join(src, entry);
    var destPath = path.join(dest, entry);
    if (fs.statSync(srcPath).isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

/**
 * Inline all CSS custom-property references.
 * Handles nested fallbacks by running multiple passes until stable.
 * Unknown variables fall back to their declared fallback value.
 */
function resolveVars(css) {
  let prev;
  do {
    prev = css;
    // 1. Replace var(--known) with its hard-coded value
    css = css.replace(/var\((--[\w-]+)\)/g, function(m, name) {
      return CSS_VARS[name] || m;
    });
    // 2. Replace var(--any, fallback): use value if known, else fallback text
    css = css.replace(/var\((--[\w-]+),\s*([^)]+)\)/g, function(m, name, fallback) {
      return CSS_VARS[name] ? CSS_VARS[name] : fallback.trim();
    });
  } while (css !== prev);
  return css;
}

/** Replace clamp(min, preferred, max) with max (bounded size for fixed tablet). */
function resolveClamp(css) {
  return css.replace(/clamp\([^,]+,\s*[^,]+,\s*([^)]+)\)/g, function(m, max) {
    return max.trim();
  });
}

/** Expand CSS inset: <val> shorthand → top/right/bottom/left. */
function resolveInset(css) {
  return css.replace(/\binset:\s*([^;{]+);/g, function(m, val) {
    var v = val.trim();
    return 'top: ' + v + '; right: ' + v + '; bottom: ' + v + '; left: ' + v + ';';
  });
}

/**
 * Remove backdrop-filter (not supported in Chrome 38).
 * Also removes the -webkit- prefixed version.
 */
function stripBackdropFilter(text) {
  return text.replace(/(-webkit-)?backdrop-filter:\s*[^;]+;/g, '');
}

/**
 * Process a CSS file:
 *   – inline custom properties
 *   – flatten clamp()
 *   – expand inset shorthand
 *   – strip backdrop-filter (unsupported in Chrome 38)
 *   – strip the now-redundant :root { } block
 */
function processCSS(css) {
  css = resolveVars(css);
  css = resolveClamp(css);
  css = resolveInset(css);
  css = stripBackdropFilter(css);
  // Remove the :root { ... } declaration block (vars are now inlined)
  css = css.replace(/:root\s*\{[^}]*\}/g, '/* :root custom properties inlined by build.js */');
  return css;
}

/** Run Babel on a JS code string. */
function processJS(code, filename) {
  var result = babel.transformSync(code, Object.assign({}, BABEL_CONFIG, { filename: filename }));
  // Also apply CSS transforms to the output: this fixes CSS embedded inside
  // JS string literals (e.g. nav.js injects a <style> block via textContent).
  var output = result.code;
  output = resolveVars(output);
  output = resolveClamp(output);
  output = resolveInset(output);
  output = stripBackdropFilter(output);
  return output;
}

/**
 * Process an HTML file:
 *   – Process inline <style> blocks (resolves vars, clamp, etc.)
 *   – Babel-transform every inline <script> block (those without src=)
 *   – Inject <script src="polyfills.js"> as the first element inside <body>
 */
function processHTML(html, filename) {
  // Process inline <style> blocks — resolves CSS vars, clamp(), inset, backdrop-filter
  html = html.replace(/<style>([\s\S]*?)<\/style>/g, function(match, css) {
    return '<style>\n' + processCSS(css) + '\n</style>';
  });
  // Only match <script> tags that have NO src= attribute
  html = html.replace(/<script>([\s\S]*?)<\/script>/g, function(match, code) {
    var compiled = processJS(code, filename + '.inline.js');
    return '<script>\n' + compiled + '\n</script>';
  });
  // Inject polyfills immediately after the opening <body> tag
  html = html.replace(/<body>/, '<body>\n  <script src="polyfills.js"></script>');
  return html;
}

// ── Polyfill bundle ──────────────────────────────────────────────────────────
/**
 * Concatenate whatwg-fetch and url-search-params-polyfill into a single file.
 * Each polyfill uses a guard so it only installs itself when the native API
 * is missing.
 */
function buildPolyfills() {
  var parts = [];

  try {
    var fetchPath = require.resolve('whatwg-fetch');
    parts.push('/* whatwg-fetch polyfill — https://github.com/github/fetch */');
    parts.push(fs.readFileSync(fetchPath, 'utf8'));
  } catch (_) {
    console.warn('[build] WARN: whatwg-fetch not found — fetch() will be unavailable on old browsers');
  }

  try {
    var uspPath = require.resolve('url-search-params-polyfill');
    parts.push('\n/* url-search-params-polyfill — https://github.com/nicktindall/cyclon.p2p */');
    parts.push(fs.readFileSync(uspPath, 'utf8'));
  } catch (_) {
    console.warn('[build] WARN: url-search-params-polyfill not found');
  }

  return parts.join('\n');
}

// ── Build ────────────────────────────────────────────────────────────────────
if (!fs.existsSync(DIST_DIR)) {
  fs.mkdirSync(DIST_DIR);
}

// 1. Write polyfills.js first
var polyfillCode = buildPolyfills();
fs.writeFileSync(path.join(DIST_DIR, 'polyfills.js'), polyfillCode, 'utf8');
console.log('[build] polyfills.js → dist/polyfills.js');

// copies static asset directories (like images) into dist/
var ASSET_DIRS = ['img'];
for (var ai = 0; ai < ASSET_DIRS.length; ai++) {
  var dirName = ASSET_DIRS[ai];
  var srcDir  = path.join(SRC_DIR, dirName);
  var destDir = path.join(DIST_DIR, dirName);
  if (fs.existsSync(srcDir)) {
    copyDir(srcDir, destDir);
    console.log('[build] copied ' + dirName + '/dist/' + dirName + '/');
  }
}

// 2. Process each source file
var entries = fs.readdirSync(SRC_DIR);
for (var i = 0; i < entries.length; i++) {
  var file = entries[i];
  if (SKIP.has(file)) continue;

  var srcPath = path.join(SRC_DIR, file);
  if (fs.statSync(srcPath).isDirectory()) continue;

  var ext = path.extname(file).toLowerCase();
  if (['.html', '.js', '.css'].indexOf(ext) === -1) continue;

  var content = fs.readFileSync(srcPath, 'utf8');
  try {
    if (ext === '.css')  content = processCSS(content);
    if (ext === '.js')   content = processJS(content, file);
    if (ext === '.html') content = processHTML(content, file);
  } catch (err) {
    console.error('[build] ERROR processing ' + file + ':', err.message);
    process.exit(1);
  }

  var destPath = path.join(DIST_DIR, file);
  fs.writeFileSync(destPath, content, 'utf8');
  console.log('[build] ' + file + ' → dist/' + file);
}

console.log('[build] Done. Compiled files are in dist/');

// Usage: node tests/report-smoke.cjs demo-output/report.html
// Checks embedded JavaScript syntax, embedded demo data, run selection, filtering,
// inspection and export wiring with a small DOM substitute. Not a browser rendering test.
const fs = require('fs');
const vm = require('vm');
const html = fs.readFileSync(process.argv[2], 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
if (scripts.length !== 1) throw new Error('Expected one embedded script');
const script = scripts[0][1];
new vm.Script(script);
const match = script.match(/^const data = (.*);$/m);
const data = JSON.parse(match[1]);
if (html.includes('/*RUN_DATA*/null')) throw new Error('Template data missing');
if (data.runs.length !== 2 || !data.comparison) throw new Error('Expected a before/after comparison report');
if (data.runs[0].status !== 'FAIL' || data.runs[1].status !== 'PASS') throw new Error('Unexpected demo run statuses');
if (data.comparison.cleared_failures.join() !== 'rail_3v3') throw new Error('Unexpected cleared failures');

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.style = {}; this.handlers = {}; this.dataset = {}; this.value = ''; this.textContent = ''; this.className = ''; this.hidden = false; this.open = false; }
  appendChild(child) { this.children.push(child); return child; }
  append(...children) { this.children.push(...children); }
  setAttribute(key, value) { this[key] = value; }
  replaceChildren(...children) { this.children = children; }
  addEventListener(event, fn) { this.handlers[event] = fn; }
  click() { if (this.handlers.click) this.handlers.click(); }
}
const nodes = new Map([...html.matchAll(/\bid="([^"]+)"/g)].map(m => [m[1], new Element(m[1])]));
nodes.get('filter').value = 'all';
const context = {
  document: {
    getElementById(id) { if (!nodes.has(id)) throw new Error('Missing HTML element: ' + id); return nodes.get(id); },
    createElement: tag => new Element(tag),
    createElementNS: (_, tag) => new Element(tag),
  },
  URL: { createObjectURL() { return 'blob:smoke-check'; }, revokeObjectURL() {} },
  Blob,
  setTimeout: fn => fn(),
};
vm.runInNewContext(script, context);
// The report opens on the retest (last run).
if (nodes.get('status').textContent !== 'PASS') throw new Error('Default run is not the retest');
if (nodes.get('rows').children.length !== 8) throw new Error('Retest table did not render all checks');
if (nodes.get('map').children.length === 0) throw new Error('Point map did not render');
if (nodes.get('repair').hidden) throw new Error('Repair comparison panel hidden');
nodes.get('run-select').value = '0';
nodes.get('run-select').handlers.change();
if (nodes.get('status').textContent !== 'FAIL') throw new Error('Run selector failed');
if (nodes.get('untested').textContent !== '3') throw new Error('Untested count failed');
nodes.get('filter').value = 'attention';
nodes.get('filter').handlers.change();
if (nodes.get('rows').children.length !== 4) throw new Error('Attention filter failed');
nodes.get('filter').value = 'all';
nodes.get('search').value = '3.3 v rail';
nodes.get('search').handlers.input();
if (nodes.get('rows').children.length !== 1) throw new Error('Search failed');
nodes.get('rows').children[0].children[6].children[0].click();
if (!nodes.get('detail').textContent.includes('"status": "FAIL"')) throw new Error('Inspect action failed');
nodes.get('export').click();
console.log(JSON.stringify({script_syntax: 'passed', embedded_runs: 2, dom_smoke: 'passed', browser_visual_test: 'not performed'}));

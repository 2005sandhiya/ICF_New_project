import test, {afterEach} from 'node:test';
import assert from 'node:assert/strict';
import {transformSync} from 'esbuild';
import Module, {createRequire} from 'node:module';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const cache = new Map();
function loadSource(filename) {
  if (!fs.existsSync(filename)) filename = ['.js', '.jsx'].map(ext => filename + ext).find(fs.existsSync);
  if (cache.has(filename)) return cache.get(filename).exports;
  const module = new Module(filename);
  cache.set(filename, module);
  module.require = specifier => specifier.startsWith('.') ? loadSource(path.resolve(path.dirname(filename), specifier)) : require(specifier);
  const result = transformSync(fs.readFileSync(filename, 'utf8'), {loader: 'jsx', format: 'cjs',
    define: {'import.meta.env.VITE_API_BASE_URL': '"http://127.0.0.1:8001"'}});
  module._compile(result.code, filename);
  return module.exports;
}
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
const components = {...loadSource(path.join(root, 'src/components/TemplatePanel.jsx')), ...loadSource(path.join(root, 'src/components/IntelligencePanels.jsx'))};
const render = (name, props) => renderToStaticMarkup(React.createElement(components[name], props));
const {validateTemplateFile, templateRequest, exportICFDocument} = loadSource(path.join(root, 'src/api/templates.js'));
const originalFetch = globalThis.fetch;
afterEach(() => {globalThis.fetch = originalFetch;});
const selection = {study_id: 'A', kind: 'default', filename: 'Default ICF layout', template_id: 'builtin-v1'};
const state = {selection, busy: false, error: '', message: '', upload() {}, remove() {}, retry() {}};
const draft = {revision: 2, sections: [{section_id: 'purpose', title: 'Purpose', content: 'Protocol text'}]};
const vm = {icfStudyId: 'A', icfResult: {study_id: 'A', revision: 2, icf_draft: draft, patient_friendly_icf: draft, template: selection},
  humanReview: {study_id: 'A', review_status: 'APPROVED', approved_revision: 2}, templateState: state};

test('optional template UI explains default and supported upload type', () => {
  const html = render('TemplatePanel', {studyId: 'A', state});
  assert.match(html, /ICF Template/); assert.match(html, /default ICF template is used/);
  assert.match(html, /accept="\.docx/); assert.match(html, /10 MB/);
});
test('custom filename, view, replacement and removal are displayed', () => {
  const html = render('TemplatePanel', {studyId: 'A', state: {...state, selection: {...selection, kind: 'custom', filename: 'hospital.docx'}}});
  for (const text of ['hospital.docx', 'View selected template', 'Replace DOCX template', 'Remove custom template']) assert.ok(html.includes(text));
});
test('invalid file errors and success messages are accessible', () => {
  assert.match(render('TemplatePanel', {studyId: 'A', state: {...state, error: 'Corrupt DOCX'}}), /role="alert"/);
  assert.match(render('TemplatePanel', {studyId: 'A', state: {...state, message: 'Template uploaded'}}), /role="status"/);
  assert.ok(validateTemplateFile({name: 'bad.pdf', size: 2}));
  assert.ok(validateTemplateFile({name: 'bad.docx', size: 0}));
  assert.ok(validateTemplateFile({name: 'bad.docx', size: 11 * 1024 * 1024}));
  assert.equal(validateTemplateFile({name: 'OK.DOCX', size: 42}), null);
});
test('PDF is primary and editable DOCX choices remain for Patient-Facing ICF', () => {
  const html = render('ExportPanel', {vm});
  for (const text of ['Download Patient-Facing PDF', 'Download Patient-Facing DOCX']) assert.ok(html.includes(text));
  assert.match(html, /Ready for export/);
});
test('pending, wrong study, stale revision and changed template lock downloads', () => {
  const cases = [
    {...vm, humanReview: {...vm.humanReview, review_status: 'PENDING'}},
    {...vm, humanReview: {...vm.humanReview, study_id: 'B'}},
    {...vm, humanReview: {...vm.humanReview, approved_revision: 1}},
    {...vm, templateState: {...state, selection: {...selection, template_id: 'new'}}},
  ];
  for (const value of cases) {
    const html = render('ExportPanel', {vm: value});
    assert.match(html, /Export locked/); assert.equal((html.match(/disabled=""/g) || []).length, 2);
  }
});
test('review shows revision history, validation and populated template preview', () => {
  const html = render('ReviewPanel', {vm: {...vm, validationResult: {study_id: 'A', revision: 2, checks: [], overall_score: 95, overall_status: 'PASSED'},
    reviewerComment: '', icfResult: {...vm.icfResult, document_preview: {standard: 'Populated document wording'}},
    revisionHistory: {revisions: [vm.icfResult], reviews: []}}});
  assert.match(html, /Populated document wording/); assert.match(html, /Revision and review history/); assert.match(html, /95.0%/);
});
test('upload API uses encoded study and multipart body; errors retain server message', async () => {
  let seen;
  globalThis.fetch = async (url, options) => {seen = {url, options}; return new Response(JSON.stringify(selection), {status: 200});};
  assert.equal((await templateRequest('A/B', 'POST', new File(['zip'], 'template.docx'))).success, true);
  assert.match(seen.url, /A%2FB$/); assert.equal(seen.options.body.get('file').name, 'template.docx');
  globalThis.fetch = async () => new Response(JSON.stringify({detail: 'Corrupt template'}), {status: 400});
  assert.equal((await templateRequest('A', 'POST')).error, 'Corrupt template');
});
test('PDF download binds study, version and revision; DOCX stays explicit', async () => {
  let url;
  globalThis.fetch = async input => {url = input; return new Response('%PDF-1.4', {headers: {'Content-Type': 'application/pdf', 'Content-Disposition': 'attachment; filename="A_Patient_Friendly_ICF_v2.pdf"'}});};
  const result = await exportICFDocument('A', 2, 'patient_friendly');
  assert.equal(result.success, true); assert.match(url, /export_type=patient_friendly&format=pdf&revision=2/);
  assert.equal(result.filename, 'A_Patient_Friendly_ICF_v2.pdf');
  globalThis.fetch = async input => {url = input; return new Response('docx', {headers: {'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}});};
  assert.equal((await exportICFDocument('A', 2, 'standard', 'docx')).success, true);
  assert.match(url, /format=docx/);
});
test('download rejects empty, wrong-format and failed conversion responses', async () => {
  globalThis.fetch = async () => new Response('', {headers: {'Content-Type': 'application/pdf'}});
  assert.equal((await exportICFDocument('A', 2)).success, false);
  globalThis.fetch = async () => new Response('html', {headers: {'Content-Type': 'text/html'}});
  assert.equal((await exportICFDocument('A', 2)).success, false);
  globalThis.fetch = async () => new Response(JSON.stringify({detail: 'LibreOffice is unavailable'}), {status: 503});
  assert.equal((await exportICFDocument('A', 2)).error, 'LibreOffice is unavailable');
});

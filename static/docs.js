'use strict';

const $ = id => document.getElementById(id);
const state = { actions: {}, spec: null, view: 'endpoints' };
const pages = { overview: 'Getting started', backups: 'Backups & copies', editing: 'File editing', reference: 'API reference', transfers: 'Accounts & transfers' };

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function navigate() {
  const name = Object.hasOwn(pages, location.hash.slice(1)) ? location.hash.slice(1) : 'overview';
  document.querySelectorAll('.page').forEach(node => node.hidden = node.id !== 'page-' + name);
  document.querySelectorAll('[data-page]').forEach(node => {
    const active = node.dataset.page === name;
    node.classList.toggle('active', active);
    if (active) node.setAttribute('aria-current', 'page'); else node.removeAttribute('aria-current');
  });
  $('mobile-page').value = name;
  document.title = pages[name] + ' · BCSFE API';
  window.scrollTo(0, 0);
}
function typeLabel(schema = {}) {
  if (schema.$ref) return schema.$ref.split('/').pop();
  if (schema.const !== undefined) return JSON.stringify(schema.const);
  if (schema.enum) return schema.enum.map(value => JSON.stringify(value)).join(' | ');
  if (schema.oneOf || schema.anyOf) return [...new Set((schema.oneOf || schema.anyOf).map(typeLabel))].join(' | ');
  if (Array.isArray(schema.type)) return schema.type.join(' | ');
  return schema.type === 'array' ? 'array<' + typeLabel(schema.items) + '>' : schema.type || 'object';
}
function parameterTable(schema) {
  const table = element('table', 'parameter-table'), body = element('tbody');
  for (const [name, value] of Object.entries(schema.properties || {})) {
    const row = element('tr'), label = element('td'); label.append(element('code', '', name));
    if ((schema.required || []).includes(name)) label.append(element('span', 'required', 'required'));
    const notes = [];
    if (value.description) notes.push(value.description);
    if (value.default !== undefined) notes.push('Default: ' + JSON.stringify(value.default));
    if (value.minimum !== undefined || value.maximum !== undefined) notes.push('Range: ' + (value.minimum ?? '…') + '–' + (value.maximum ?? '…'));
    if (value.format) notes.push('Format: ' + value.format);
    row.append(label, element('td', '', typeLabel(value)), element('td', 'parameter-note', notes.join(' '))); body.append(row);
  }
  table.append(body); return table;
}
function resolvedSchema(schema, seen = new Set()) {
  if (!schema || typeof schema !== 'object') return schema;
  if (Array.isArray(schema)) return schema.map(value => resolvedSchema(value, seen));
  if (schema.$ref?.startsWith('#/components/schemas/') && !seen.has(schema.$ref)) {
    const name = schema.$ref.slice('#/components/schemas/'.length);
    const target = state.spec?.components?.schemas?.[name];
    if (target) return resolvedSchema(target, new Set([...seen, schema.$ref]));
  }
  return Object.fromEntries(Object.entries(schema).map(([key, value]) => [key, resolvedSchema(value, seen)]));
}
function schemaDetails(title, schema) {
  const node = element('details', 'schema-details');
  node.append(element('summary', '', title), element('pre', '', JSON.stringify(resolvedSchema(schema), null, 2)));
  return node;
}
function renderReference() {
  const query = $('reference-search').value.trim().toLowerCase(), group = $('action-group').value;
  $('reference-list').replaceChildren(); $('action-group').hidden = state.view !== 'actions';
  const entries = state.view === 'actions' ? Object.entries(state.actions).sort().map(([name, value]) => ({ name, description: value.description, schema: value.schema, source: value.source, action: true })) :
    Object.entries(state.spec?.paths || {}).flatMap(([path, methods]) => Object.entries(methods).filter(([method]) => ['get', 'post', 'delete', 'put', 'patch'].includes(method)).map(([method, value]) => ({ name: path, method, description: value.summary, operation: value })));
  for (const entry of entries) {
    if (!(entry.name + ' ' + entry.description).toLowerCase().includes(query)) continue;
    if (entry.action && group !== 'all' && entry.name.split('.')[0] !== group) continue;
    const details = element('details', 'reference-item'), summary = element('summary');
    if (!entry.action) summary.append(element('span', 'method ' + entry.method, entry.method.toUpperCase()));
    summary.append(element('code', '', entry.name), element('span', 'reference-description', entry.description)); details.append(summary);
    const body = element('div', 'reference-body'); body.append(element('p', '', entry.description));
    if (entry.action) {
      body.append(element('h3', '', 'Arguments'), parameterTable(entry.schema), schemaDetails('Full argument schema', entry.schema));
      body.append(element('p', '', 'Use this action name and its arguments in operations for POST /v2/save/edit.'));
    } else {
      const operation = entry.operation;
      if (operation.description) body.append(element('p', '', operation.description));
      body.append(element('p', '', operation.security?.length ? 'Authentication: Bearer API key.' : 'Authentication: no API key required.'));
      if (operation.parameters?.length) {
        const schema = { properties: {}, required: [] };
        for (const parameter of operation.parameters) {
          schema.properties[parameter.name] = { ...parameter.schema, description: parameter.in + ' parameter. ' + (parameter.description || parameter.schema?.description || '') };
          if (parameter.required) schema.required.push(parameter.name);
        }
        body.append(element('h3', '', 'Parameters'), parameterTable(schema));
      }
      for (const [mime, content] of Object.entries(operation.requestBody?.content || {})) {
        body.append(element('h3', '', 'Request · ' + mime));
        if (content.schema) body.append(parameterTable(content.schema), schemaDetails('Full request schema', content.schema));
      }
      body.append(element('h3', '', 'Responses'));
      const responses = element('table'), tbody = element('tbody');
      for (const [status, response] of Object.entries(operation.responses || {})) {
        const row = element('tr'), content = element('td'); content.append(element('span', '', response.description));
        for (const [mime, value] of Object.entries(response.content || {})) {
          content.append(element('p', '', mime));
          if (value.schema) content.append(schemaDetails('Response schema', value.schema));
        }
        row.append(element('td', '', status), content); tbody.append(row);
      }
      responses.append(tbody); body.append(responses);
    }
    if (entry.source) body.append(element('p', 'source-note', 'Source: ' + entry.source));
    details.append(body); $('reference-list').append(details);
  }
  $('reference-feedback').textContent = $('reference-list').children.length ? '' : 'No matching actions or endpoints.';
}
async function loadReference() {
  try {
    const get = async path => { const response = await fetch(path, { redirect: 'error' }); if (!response.ok) throw new Error('Could not load the API reference (HTTP ' + response.status + ').'); return response.json(); };
    const [features, spec] = await Promise.all([get('/v2/features'), get('/openapi.json')]);
    state.actions = features.actions; state.spec = spec; $('action-count').textContent = Object.keys(state.actions).length;
    for (const group of [...new Set(Object.keys(state.actions).map(name => name.split('.')[0]))].sort()) { const option = element('option', '', group); option.value = group; $('action-group').append(option); }
    const counts = features.features.counts;
    $('coverage-summary').textContent = counts.source_features + ' source menu features mapped to ' + counts.registered_typed_actions + ' edit actions and file/account endpoints. Device-only and terminal-only operations are listed separately.';
    renderReference();
  } catch (error) { $('reference-feedback').textContent = error.message; }
}

window.addEventListener('hashchange', navigate);
$('mobile-page').addEventListener('change', event => location.hash = event.target.value);
$('reference-search').addEventListener('input', renderReference);
$('action-group').addEventListener('change', renderReference);
for (const view of ['actions', 'endpoints']) $('show-' + view).addEventListener('click', () => {
  state.view = view;
  $('show-actions').classList.toggle('selected', view === 'actions');
  $('show-endpoints').classList.toggle('selected', view === 'endpoints');
  renderReference();
});
document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
  try { await navigator.clipboard.writeText($(button.dataset.copy).textContent); button.textContent = 'Copied'; }
  catch { button.textContent = 'Select code to copy'; }
}));
$('base-url').textContent = location.origin;
navigate(); loadReference();

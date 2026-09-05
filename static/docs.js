'use strict';

const $ = id => document.getElementById(id);
const pages = { overview: 'Getting started', backups: 'Backups & copies', editing: 'File editing', reference: 'API reference', transfers: 'Accounts & transfers', metadata: 'Metadata & configuration', coverage: 'Source feature coverage' };
const state = { actions: {}, spec: null, features: null, actionDocs: {categories: [], actions: {}}, endpointDocs: {categories: [], endpoints: {}}, view: 'endpoints', ready: false, opened: new Set(), entryNodes: new Map() };
const statusNames = { implemented: 'Implemented', adapted: 'Adapted for HTTP', unavailable_in_vercel: 'Unavailable on Vercel', not_applicable_to_http: 'Not applicable to HTTP', binding_missing: 'Missing binding' };
const featureGroups = { gameplay: 'Game editing', file_account: 'Save files & transfers', account: 'Account operations', editor_metadata: 'Metadata & configuration', device_cli: 'Device operations', editor_cli: 'Terminal controls' };

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function route() {
  const [name, query = ''] = location.hash.slice(1).split('?');
  return { page: Object.hasOwn(pages, name) ? name : 'overview', params: new URLSearchParams(query) };
}
function referenceLink(view, values = {}) {
  const params = new URLSearchParams({view, ...values});
  return '#reference?' + params.toString();
}
function navigate() {
  const current = route(), name = current.page;
  document.querySelectorAll('.page').forEach(node => node.hidden = node.id !== 'page-' + name);
  document.querySelectorAll('[data-page]').forEach(node => {
    const active = node.dataset.page === name; node.classList.toggle('active', active);
    if (active) node.setAttribute('aria-current', 'page'); else node.removeAttribute('aria-current');
  });
  $('category-sidebar').hidden = name !== 'reference';
  $('mobile-page').value = name; document.title = pages[name] + ' · BCSFE API';
  if (name === 'reference') {
    const view = current.params.get('view'); if (view === 'actions' || view === 'endpoints') state.view = view;
    populateCategories(current.params.get('category') || 'all');
    $('reference-search').value = current.params.get('q') || '';
    const entry = current.params.get('entry');
    if (entry) { state.opened.add(state.view + ':' + entry); $('reference-category').value = 'all'; $('reference-search').value = ''; }
    renderReference();
    if (entry && state.entryNodes.has(entry)) { state.entryNodes.get(entry).scrollIntoView({block: 'start'}); return; }
  }
  window.scrollTo(0, 0);
}
function resolveRoot(schema = {}) {
  const seen = new Set();
  while (schema.$ref?.startsWith('#/components/schemas/') && !seen.has(schema.$ref)) {
    seen.add(schema.$ref); const target = state.spec?.components?.schemas?.[schema.$ref.split('/').pop()];
    if (!target) break; schema = target;
  }
  return schema;
}
function resolvedSchema(schema, seen = new Set()) {
  if (!schema || typeof schema !== 'object') return schema;
  if (Array.isArray(schema)) return schema.map(value => resolvedSchema(value, seen));
  if (schema.$ref?.startsWith('#/components/schemas/') && !seen.has(schema.$ref)) {
    const target = state.spec?.components?.schemas?.[schema.$ref.split('/').pop()];
    if (target) return resolvedSchema(target, new Set([...seen, schema.$ref]));
  }
  return Object.fromEntries(Object.entries(schema).map(([key, value]) => [key, resolvedSchema(value, seen)]));
}
function typeLabel(schema = {}) {
  if (schema.$ref) return schema.$ref.split('/').pop();
  if (schema.const !== undefined) return JSON.stringify(schema.const);
  if (schema.enum) return schema.enum.map(value => JSON.stringify(value)).join(' | ');
  if (schema.oneOf || schema.anyOf) return [...new Set((schema.oneOf || schema.anyOf).map(typeLabel))].join(' | ');
  if (Array.isArray(schema.type)) return schema.type.join(' | ');
  return schema.type === 'array' ? 'array<' + typeLabel(schema.items) + '>' : schema.type || 'object';
}
function parameterTable(input) {
  const schema = resolveRoot(input), properties = schema.properties || {};
  if (!Object.keys(properties).length) return element('p', 'example-note', schema.oneOf || schema.anyOf ? 'Choose a matching structure from the full schema below.' : 'No named fields are required here. See the schema for the exact format.');
  const table = element('table', 'parameter-table'), head = element('thead'), header = element('tr'), body = element('tbody');
  for (const title of ['Field', 'Type', 'Description & constraints']) header.append(element('th', '', title)); head.append(header);
  for (const [name, value] of Object.entries(properties)) {
    const row = element('tr'), label = element('td'); label.append(element('code', '', name));
    if ((schema.required || []).includes(name)) label.append(element('span', 'required', 'required'));
    const info = element('td', 'parameter-note');
    if (value.description) info.append(element('span', 'field-description', value.description));
    const notes = [];
    if (value.default !== undefined) notes.push('Default: ' + JSON.stringify(value.default));
    if (value.minimum !== undefined || value.maximum !== undefined) notes.push('Range: ' + (value.minimum ?? '…') + '–' + (value.maximum ?? '…'));
    if (value.minItems !== undefined || value.maxItems !== undefined) notes.push('Items: ' + (value.minItems ?? 0) + '–' + (value.maxItems ?? '…'));
    if (value.minLength !== undefined || value.maxLength !== undefined) notes.push('Length: ' + (value.minLength ?? 0) + '–' + (value.maxLength ?? '…'));
    if (value.format) notes.push('Format: ' + value.format);
    if (value.pattern) notes.push('Pattern: ' + value.pattern);
    if (!value.description && !notes.length) notes.push((schema.required || []).includes(name) ? 'Provide this field.' : 'Optional; omit to use the endpoint or action behavior described above.');
    info.append(element('span', '', notes.join(' · ')));
    row.append(label, element('td', '', typeLabel(value)), info); body.append(row);
  }
  table.append(head, body); return table;
}
function schemaDetails(title, schema) {
  const node = element('details', 'schema-details'); node.append(element('summary', '', title));
  node.addEventListener('toggle', () => { if (node.open && node.children.length === 1) node.append(element('pre', '', JSON.stringify(resolvedSchema(schema), null, 2))); });
  return node;
}
async function copyText(button, text) {
  try { await navigator.clipboard.writeText(text); button.textContent = 'Copied'; }
  catch { button.textContent = 'Select code to copy'; }
}
function codeBlock(title, text) {
  const block = element('div', 'code-sample'), bar = element('div', 'code-label'), button = element('button', 'copy-code', 'Copy'); button.type = 'button';
  button.addEventListener('click', () => copyText(button, text)); bar.append(element('span', 'sample-label', title), button);
  block.append(bar, element('pre', '', text)); return block;
}
function authInfo(operation) {
  if (!operation.security?.length) return {label: 'Public · no API key', key: null, header: null};
  if (operation.security.some(item => Object.hasOwn(item, 'BackupToken'))) return {label: 'Private backup · X-Backup-Token', key: 'BACKUP_TOKEN', header: 'X-Backup-Token'};
  return {label: 'Operator only · TEMPLATE_API_KEY', key: 'TEMPLATE_API_KEY', header: 'Authorization'};
}
function curlExample(entry) {
  const auth = authInfo(entry.operation);
  let path = entry.path.replace(/\{([a-z_]+)\}/g, (_, key) => '$' + key.toUpperCase());
  const query = new URLSearchParams(entry.doc.query_example || {}); if (query.size) path += '?' + query;
  const lines = ['curl --request ' + entry.method.toUpperCase() + ' "$API_URL' + path + '"'];
  if (auth.header === 'X-Backup-Token') lines.push('  -H "X-Backup-Token: $' + auth.key + '"');
  if (auth.header === 'Authorization') lines.push('  -H "Authorization: Bearer $' + auth.key + '"');
  if (entry.doc.example !== undefined) {
    const json = JSON.stringify(entry.doc.example, null, 2).replace(/'/g, "'\"'\"'");
    lines.push('  -H "Content-Type: application/json"', "  --data '" + json + "'");
  }
  const successContent = Object.entries(entry.operation.responses || {}).filter(([code]) => /^2/.test(code)).map(([, response]) => response.content || {});
  if (entry.doc.example?.output === 'file' || successContent.some(content => content['application/octet-stream'] && !content['application/json'])) lines.push('  --output result.save');
  return lines.join(' \\\n');
}
function entries() {
  if (state.view === 'actions') return Object.entries(state.actions).sort().map(([key, value]) => {
    const doc = state.actionDocs.actions[key] || {}; return {key, name: key, action: true, schema: value.schema, source: value.source, doc, category: doc.category || 'other', description: doc.description || value.description};
  });
  return Object.entries(state.spec?.paths || {}).flatMap(([path, methods]) => Object.entries(methods).filter(([method]) => ['get','post','delete','put','patch'].includes(method)).map(([method, operation]) => {
    const key = method.toUpperCase() + ' ' + path, doc = state.endpointDocs.endpoints[key] || {};
    return {key, name: path, path, method, operation, doc, category: doc.category || 'other', description: doc.description || operation.summary};
  }));
}
function categories() { return state.view === 'actions' ? state.actionDocs.categories : state.endpointDocs.categories; }
function populateCategories(selected = 'all') {
  $('reference-category').replaceChildren(); const all = element('option', '', 'All categories'); all.value = 'all'; $('reference-category').append(all);
  for (const category of categories()) { const option = element('option', '', category.title); option.value = category.id; $('reference-category').append(option); }
  $('reference-category').value = [...$('reference-category').options].some(item => item.value === selected) ? selected : 'all';
}
function renderCategoryNavigation(allEntries) {
  $('reference-categories').replaceChildren(); $('category-sidebar-title').textContent = state.view === 'actions' ? 'EDIT CATEGORIES' : 'ENDPOINT CATEGORIES';
  for (const category of categories()) {
    const link = element('a'), count = allEntries.filter(entry => entry.category === category.id).length;
    link.href = referenceLink(state.view, {category: category.id}); link.append(element('span', '', category.title), element('span', 'category-count', count));
    link.classList.toggle('active', $('reference-category').value === category.id); $('reference-categories').append(link);
  }
}
function renderEntry(entry) {
  const details = element('details', 'reference-item'), summary = element('summary'); details.dataset.entry = entry.key;
  if (!entry.action) summary.append(element('span', 'method ' + entry.method, entry.method.toUpperCase()));
  summary.append(element('code', '', entry.name), element('span', 'reference-description', entry.action ? state.actions[entry.key].description : entry.operation.summary));
  details.append(summary); const body = element('div', 'reference-body'); body.append(element('p', '', entry.description));
  const meta = element('div', 'entry-meta'), permalink = element('a', 'entry-link', 'Link to this ' + (entry.action ? 'action' : 'endpoint'));
  permalink.href = referenceLink(state.view, {entry: entry.key});
  meta.append(element('span', 'auth-label', entry.action ? 'Operation for POST /v2/save/edit' : authInfo(entry.operation).label), permalink); body.append(meta);
  if (entry.doc.notes?.length) { const list = element('ul'); for (const note of entry.doc.notes) list.append(element('li', '', note)); body.append(list); }
  if (entry.action) {
    body.append(element('h3', '', 'Arguments'), parameterTable(entry.schema), schemaDetails('Full argument schema, including nested selectors', entry.schema));
    if (entry.doc.example) {
      body.append(codeBlock('Operation example', JSON.stringify(entry.doc.example, null, 2)));
      const full = element('details', 'schema-details'); full.append(element('summary', '', 'Complete edit request'));
      full.append(codeBlock('POST /v2/save/edit · application/json', JSON.stringify({country_code:'kr', save_base64:'BASE64_OF_SAVE_FILE', operations:[entry.doc.example]}, null, 2))); body.append(full);
      body.append(element('p', 'example-note', 'Example IDs and values are illustrative. Use IDs present in your save and prepare metadata when this action requires it.'));
    }
  } else {
    const operation = entry.operation;
    if (operation.description && operation.description !== entry.description) body.append(element('p', '', operation.description));
    if (operation.parameters?.length) {
      const schema = {properties: {}, required: []};
      for (const parameter of operation.parameters) { schema.properties[parameter.name] = {...parameter.schema, description: parameter.in + ' parameter. ' + (parameter.description || parameter.schema?.description || '')}; if (parameter.required) schema.required.push(parameter.name); }
      body.append(element('h3', '', 'Parameters'), parameterTable(schema));
    }
    for (const [mime, content] of Object.entries(operation.requestBody?.content || {})) {
      body.append(element('h3', '', 'Request body · ' + mime));
      if (content.schema) body.append(parameterTable(content.schema), schemaDetails('Full request schema', content.schema));
    }
    body.append(codeBlock('Request example · cURL', curlExample(entry)));
    body.append(element('p', 'example-note', 'Set API_URL to your Vercel origin and replace sample IDs, tokens and Base64 data before running this request.'));
    if (entry.doc.response_example !== undefined) body.append(codeBlock('Response example · illustrative values', typeof entry.doc.response_example === 'string' ? entry.doc.response_example : JSON.stringify(entry.doc.response_example, null, 2)));
    body.append(element('h3', '', 'Response contracts'));
    const table = element('table', 'response-table'), tbody = element('tbody');
    for (const [status, response] of Object.entries(operation.responses || {})) {
      const row = element('tr'), content = element('td'); content.append(element('span', '', response.description));
      for (const [mime, value] of Object.entries(response.content || {})) { content.append(element('p', 'example-note', mime)); if (value.schema) content.append(schemaDetails('Response schema', value.schema)); }
      row.append(element('td', '', status), content); tbody.append(row);
    }
    table.append(tbody); body.append(table);
  }
  if (entry.source) body.append(element('p', 'source-note', 'BCSFE source: ' + entry.source));
  details.append(body); details.open = state.opened.has(state.view + ':' + entry.key);
  const view = state.view; details.addEventListener('toggle', () => details.open ? state.opened.add(view + ':' + entry.key) : state.opened.delete(view + ':' + entry.key));
  state.entryNodes.set(entry.key, details); return details;
}
function renderReference() {
  const query = $('reference-search').value.trim().toLowerCase(), category = $('reference-category').value, all = entries();
  $('show-actions').classList.toggle('selected', state.view === 'actions'); $('show-endpoints').classList.toggle('selected', state.view === 'endpoints');
  $('show-actions').setAttribute('aria-pressed', String(state.view === 'actions')); $('show-endpoints').setAttribute('aria-pressed', String(state.view === 'endpoints'));
  $('reference-list').replaceChildren(); state.entryNodes.clear(); renderCategoryNavigation(all);
  const filtered = all.filter(entry => (category === 'all' || entry.category === category) && (entry.key + ' ' + entry.description + ' ' + (entry.doc.notes || []).join(' ') + ' ' + JSON.stringify(entry.schema?.properties || entry.operation?.requestBody || {})).toLowerCase().includes(query));
  for (const group of [...categories(), {id:'other', title:'Other', description:''}]) {
    const matches = filtered.filter(entry => entry.category === group.id); if (!matches.length) continue;
    const section = element('section', 'reference-category'), heading = element('h2', '', group.title);
    heading.append(element('span', 'category-count', matches.length)); section.append(heading, element('p', 'category-description', group.description));
    for (const entry of matches) section.append(renderEntry(entry)); $('reference-list').append(section);
  }
  $('reference-feedback').textContent = state.ready ? filtered.length + ' of ' + all.length + ' ' + (state.view === 'actions' ? 'actions' : 'endpoints') + (filtered.length ? '' : ' · no matches') : 'Loading reference…';
  $('clear-filters').hidden = !query && category === 'all';
  $('reference-help').textContent = state.view === 'actions' ? 'Add an action and its args to operations in POST /v2/save/edit. These are edit instructions, not separate URL routes.' : 'Examples run against your API origin. Account and transfer requests can create or modify remote accounts; their recovery behavior is documented per endpoint.';
}
function renderDirectory() {
  const holder = $('category-directory'); holder.replaceChildren();
  for (const [view, catalog, records] of [['endpoints',state.endpointDocs,state.endpointDocs.endpoints],['actions',state.actionDocs,state.actionDocs.actions]]) {
    for (const category of catalog.categories) {
      const link = element('a'); link.href = referenceLink(view, {category: category.id});
      const count = Object.values(records).filter(item => item.category === category.id).length;
      link.append(element('strong', '', category.title), element('span', 'category-count', count + (view === 'actions' ? (count === 1 ? ' action' : ' actions') : (count === 1 ? ' endpoint' : ' endpoints'))), element('p', '', category.description)); holder.append(link);
    }
  }
}
function renderCoverage() {
  if (!state.features) return;
  const query = $('coverage-search').value.trim().toLowerCase(), status = $('coverage-status').value;
  $('coverage-list').replaceChildren();
  for (const [category, title] of Object.entries(featureGroups)) {
    const items = state.features.items.filter(item => item.category === category && (status === 'all' || item.implementation === status) && (item.id + ' ' + item.actions.join(' ') + ' ' + item.notes.join(' ')).toLowerCase().includes(query));
    if (!items.length) continue; $('coverage-list').append(element('h2', '', title + ' · ' + items.length));
    for (const item of items) {
      const row = element('article', 'coverage-feature'), heading = element('h3', '', item.menu_key.replace(/_/g,' '));
      heading.append(element('span','status-label',statusNames[item.implementation] || item.implementation)); row.append(heading);
      const bindings = element('div','coverage-bindings');
      for (const action of item.actions) { const link = element('a','',action); link.href = referenceLink('actions',{entry:action}); bindings.append(link); }
      if (!item.actions.length) for (const endpoint of item.endpoints) { const key = endpoint.method + ' ' + endpoint.path, link = element('a','',key); link.href = referenceLink('endpoints',{entry:key}); bindings.append(link); }
      row.append(bindings);
      for (const note of item.notes) row.append(element('p','',note));
      row.append(element('p','source-note','Source menu: ' + item.menu_paths.map(path=>path.join(' → ')).join(' / ')));
      if (item.verification.live_game_server === 'not_verified') row.append(element('p','example-note','Live game-server acceptance remains unverified.'));
      $('coverage-list').append(row);
    }
  }
  if (!$('coverage-list').children.length) $('coverage-list').append(element('p','reference-help','No matching source features.'));
}
async function loadReference() {
  try {
    const get = async path => { const response = await fetch(path,{redirect:'error'}); if (!response.ok) throw new Error('Could not load the API reference (HTTP '+response.status+').'); return response.json(); };
    const [features, spec, actionDocs, endpointDocs] = await Promise.all([get('/v2/features'),get('/openapi.json'),get('/static/action-docs.json'),get('/static/endpoint-docs.json')]);
    Object.assign(state,{actions:features.actions,spec,features:features.features,actionDocs,endpointDocs,ready:true});
    $('action-count').textContent = Object.keys(state.actions).length; $('endpoint-count').textContent = Object.keys(endpointDocs.endpoints).length;
    const counts = state.features.counts;
    $('coverage-summary').textContent = counts.source_features+' source menu features, '+counts.registered_typed_actions+' typed edit actions. See Source feature coverage for every mapping and host limitation.';
    $('coverage-counts').textContent = counts.source_features+' source features · '+counts.registered_typed_actions+' edit actions · '+counts.by_implementation.implemented+' implemented · '+counts.by_implementation.adapted+' adapted';
    $('verification-scope').textContent = state.features.verification_scope;
    for (const limit of state.features.limitations) $('coverage-limits').append(element('li','',limit));
    renderDirectory(); renderCoverage(); navigate();
  } catch (error) { $('reference-feedback').textContent = error.message; $('category-directory').textContent = error.message; }
}

window.addEventListener('hashchange',navigate);
$('mobile-page').addEventListener('change',event=>location.hash=event.target.value);
$('reference-search').addEventListener('input',()=>{ history.replaceState(null,'',referenceLink(state.view,{category:$('reference-category').value,q:$('reference-search').value})); renderReference(); });
$('reference-category').addEventListener('change',()=>location.hash=referenceLink(state.view,{category:$('reference-category').value,q:$('reference-search').value}));
for (const view of ['actions','endpoints']) $('show-'+view).addEventListener('click',()=>location.hash=referenceLink(view));
$('clear-filters').addEventListener('click',()=>{ $('reference-search').value=''; $('reference-category').value='all'; history.replaceState(null,'',referenceLink(state.view)); renderReference(); });
$('coverage-search').addEventListener('input',renderCoverage); $('coverage-status').addEventListener('change',renderCoverage);
document.querySelectorAll('[data-copy]').forEach(button=>button.addEventListener('click',()=>copyText(button,$(button.dataset.copy).textContent)));
$('theme-select').value=window.docsTheme?.get() || 'system';
$('theme-select').addEventListener('change',event=>window.docsTheme?.set(event.target.value));
$('base-url').textContent=location.origin;
navigate(); loadReference();

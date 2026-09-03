'use strict';

const $ = id => document.getElementById(id);
const state = { key: '', editorKey: '', backups: new Map(), backupCursor: null, historyCursor: null,
  actions: {}, spec: null, referenceView: 'actions', clone: null, cloneBusy: false, backupBusy: false, historyBusy: false };
const regionNames = { kr: 'KR', en: 'EN', jp: 'JP', tw: 'TW' };
const groupNames = { items: 'Resources & items', cats: 'Cats', stages: 'Stages', skills: 'Special skills',
  gatya: 'Gacha', gamatoto: 'Gamatoto', ototo: 'Ototo', account: 'Account fields', save: 'Save format',
  fixes: 'Repairs', lineups: 'Lineups', shrine: 'Cat shrine', rewards: 'Rewards', missions: 'Missions',
  medals: 'Medals', enemy_guide: 'Enemy guide', gambling: 'Events', playtime: 'Play time' };

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function feedback(id, text = '', kind = '') { const node = $(id); node.textContent = text; node.className = 'feedback' + (kind ? ' ' + kind : ''); }
function storageGet(key) { try { return JSON.parse(sessionStorage.getItem(key)); } catch { return null; } }
function storageSet(key, value) { try { value == null ? sessionStorage.removeItem(key) : sessionStorage.setItem(key, JSON.stringify(value)); } catch { /* The page also works when storage is disabled. */ } }
function message(error) {
  let text = error.message || 'The request could not be completed.';
  for (const key of [state.key, state.editorKey]) if (key) text = text.split(key).join('[hidden]');
  return text;
}
class APIError extends Error { constructor(text, status, data) { super(text); this.status = status; this.data = data || {}; } }
async function api(path, options = {}) {
  const key = options.kind === 'editor' ? (state.editorKey || state.key) : state.key;
  const headers = { Accept: options.binary ? 'application/octet-stream' : 'application/json' };
  if (key) headers.Authorization = 'Bearer ' + key;
  let body = options.body;
  if (body && !(body instanceof FormData)) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(body); }
  let response;
  try { response = await fetch(path, { method: options.method || 'GET', headers, body, redirect: 'error' }); }
  catch { throw new APIError('Could not reach the API. Check your connection before trying again.', 0); }
  if (!response.ok) {
    let data = {};
    try { data = await response.json(); } catch { /* Keep the HTTP status if the response is not JSON. */ }
    throw new APIError(data.message || 'Request failed (HTTP ' + response.status + ').', response.status, data);
  }
  if (options.binary) return response.blob();
  const result = await response.json();
  if (result.success !== true) throw new APIError(result.message || 'The API did not confirm success.', response.status, result);
  return result;
}
function requireKey(kind = 'backup') {
  if (kind === 'editor' ? (state.editorKey || state.key) : state.key) return true;
  openAuth(); return false;
}
function updateConnection() {
  const connected = !!(state.key || state.editorKey);
  $('connection-label').textContent = connected ? 'Connected' : 'Connect';
  $('connection-dot').classList.toggle('connected', connected);
}
function openAuth() {
  $('api-key').value = state.key; $('editor-key').value = state.editorKey;
  feedback('auth-feedback'); $('auth-dialog').showModal();
  $('api-key').focus();
}
function pageName() { const value = location.hash.slice(1); return ['backups', 'editor', 'overview', 'reference', 'transfers'].includes(value) ? value : 'backups'; }
function navigate() {
  const name = pageName();
  document.querySelectorAll('.page').forEach(node => node.hidden = node.id !== 'page-' + name);
  document.querySelectorAll('[data-page]').forEach(node => { node.classList.toggle('active', node.dataset.page === name); if (node.dataset.page === name) node.setAttribute('aria-current', 'page'); else node.removeAttribute('aria-current'); });
  $('mobile-page').value = name;
  document.title = ({ backups: 'Backups', editor: 'Save editor', overview: 'Getting started', reference: 'API reference', transfers: 'Accounts & transfers' })[name] + ' · BCSFE API';
}
function dateLabel(value) { if (!value) return '—'; const date = new Date(value); return Number.isNaN(+date) ? '—' : date.toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric' }); }
function versionLabel(value) { const n = Number(value); return Number.isInteger(n) ? Math.floor(n / 10000) + '.' + Math.floor(n % 10000 / 100) + '.' + n % 100 : '—'; }
function safeName(name) { return (name || 'backup').replace(/[<>:"/\\|?*\x00-\x1f]/g, '-').slice(0, 100); }
function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob), link = element('a');
  link.href = url; link.download = name; document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
function blobFromBase64(value) { return new Blob([Uint8Array.from(atob(value), c => c.charCodeAt(0))], { type: 'application/octet-stream' }); }
function downloadButton(text, callback) {
  const button = element('button', 'button small', text); button.type = 'button';
  button.addEventListener('click', async () => { button.disabled = true; try { await callback(); } finally { button.disabled = false; } });
  return button;
}
async function downloadPath(path, filename) {
  try { saveBlob(await api(path, { binary: true }), filename); }
  catch (error) { feedback('library-feedback', message(error), 'error'); }
}
async function hydrate(items, endpoint, idKey) {
  const result = []; let position = 0;
  await Promise.all(Array.from({ length: Math.min(3, items.length) }, async () => {
    while (position < items.length) { const item = items[position++], id = item[idKey];
      try { result.push(await api(endpoint + encodeURIComponent(id))); }
      catch (error) { result.push({ ...item, load_error: message(error) }); }
    }
  }));
  const order = new Map(items.map((item, index) => [item[idKey], index]));
  return result.sort((a, b) => order.get(a[idKey]) - order.get(b[idKey]));
}
function renderBackups() {
  $('backup-list').replaceChildren();
  for (const backup of state.backups.values()) {
    const row = element('tr'), name = element('td'), title = element('div', 'backup-title', backup.name || 'Backup');
    name.append(title, element('div', 'backup-subtitle', backup.load_error ? 'Details unavailable' : backup.bytes ? Math.max(1, Math.round(backup.bytes / 1024)) + ' KB' : ''));
    const region = element('td'); region.append(element('span', 'region-tag', regionNames[backup.country_code] || '—'));
    row.append(name, region, element('td', 'wide-only', versionLabel(backup.game_version)), element('td', 'wide-only', dateLabel(backup.created_at)));
    const actions = element('td'), buttons = element('div', 'row-actions');
    const download = element('button', 'link-button', 'Download'); download.type = 'button';
    download.addEventListener('click', () => downloadPath('/v1/templates/' + encodeURIComponent(backup.template_id) + '/download', safeName(backup.name) + '.save'));
    const clone = element('button', 'link-button', 'Create copy'); clone.type = 'button'; clone.disabled = backup.clone_ready !== true;
    if (clone.disabled) clone.title = 'This backup must pass the save format check before it can be copied.';
    clone.addEventListener('click', () => openClone(backup)); buttons.append(download, clone); actions.append(buttons); row.append(actions); $('backup-list').append(row);
  }
  $('backup-empty').hidden = state.backups.size > 0;
  $('connect-library').hidden = !!state.key;
  $('backup-empty').querySelector('p').textContent = state.key ? (state.backupCursor ? 'No backups on this page. Load more to keep looking.' : 'No backups yet. Save a file above to get started.') : 'Connect an API key to view your backups.';
  $('more-backups').hidden = !state.backupCursor;
}
async function loadBackups(append = false, initial = null) {
  if (!state.key) { renderBackups(); return; }
  if (state.backupBusy) return;
  state.backupBusy = true; $('refresh-backups').disabled = true; $('more-backups').disabled = true;
  feedback('library-feedback', 'Loading backups…');
  try {
    const result = initial || await api('/v1/templates' + (append && state.backupCursor ? '?cursor=' + encodeURIComponent(state.backupCursor) : ''));
    const records = await hydrate(result.templates || [], '/v1/templates/', 'template_id');
    if (!append) state.backups.clear();
    for (const record of records) state.backups.set(record.template_id, record);
    state.backupCursor = result.next_cursor;
    renderBackups();
    const failures = records.filter(record => record.load_error).length;
    feedback('library-feedback', failures ? failures + ' backup details could not be loaded. Refresh to try again.' : '', failures ? 'error' : '');
  } catch (error) { feedback('library-feedback', message(error), 'error'); }
  finally { state.backupBusy = false; $('refresh-backups').disabled = false; $('more-backups').disabled = false; }
}
function selectedBackupFile() {
  const file = $('backup-file').files[0];
  if (!file) throw new Error('Choose a save file first.');
  if (file.size > 1024 * 1024) throw new Error('The save file must be 1 MB or smaller.');
  return file;
}
function setFileLabel() {
  const file = $('backup-file').files[0];
  $('backup-file-label').textContent = file ? file.name : 'Choose a save file';
  $('backup-file-hint').textContent = file ? Math.max(1, Math.round(file.size / 1024)) + ' KB · ready to save' : 'or drop it here · SAVE_DATA, .save, .sav';
  if (file && !$('backup-name').value) $('backup-name').value = file.name.replace(/\.(sav|save|dat)$/i, '').slice(0, 100);
  feedback('backup-feedback');
}
async function saveBackup(event) {
  event.preventDefault(); let file;
  try { file = selectedBackupFile(); } catch (error) { feedback('backup-feedback', error.message, 'error'); return; }
  if (!requireKey()) return;
  $('save-backup').disabled = true; feedback('backup-feedback', 'Saving backup…');
  const body = new FormData(); body.append('file', file); body.append('country_code', $('backup-region').value); body.append('name', $('backup-name').value.trim() || file.name.slice(0, 100));
  try {
    const result = await api('/v1/templates', { method: 'POST', body });
    state.backups = new Map([[result.template_id, result], ...state.backups]); renderBackups();
    feedback('backup-feedback', '“' + result.name + '” saved. ' + (regionNames[result.country_code] || result.country_code) + ' · ' + versionLabel(result.game_version), 'success');
  } catch (error) { feedback('backup-feedback', message(error) + (error.status === 0 || error.status >= 500 ? ' Refresh the library before uploading again.' : ''), 'error'); }
  finally { $('save-backup').disabled = false; }
}
function pendingCopy() { return storageGet('bcsfe.pending-copy'); }
function renderPending() {
  const pending = pendingCopy(); if (!pending) return;
  const panel = $('copy-result'); panel.hidden = false; panel.className = 'result-panel needs-review'; panel.replaceChildren(element('h2', '', 'A copy request needs review'), element('p', '', 'Check copy history or the recovery record before creating another copy.'), element('p', 'muted', 'Order reference: ' + pending.order_id));
  const buttons = element('div', 'result-actions');
  buttons.append(downloadButton('Check copy history', async () => { $('copy-history').open = true; await loadHistory(); }));
  if (pending.recovery_id) buttons.append(downloadButton('Download recovery', () => downloadPath('/v1/recoveries/' + encodeURIComponent(pending.recovery_id) + '/download', 'recovery.save')));
  buttons.append(downloadButton('I have reviewed this request', async () => { storageSet('bcsfe.pending-copy', null); panel.hidden = true; }));
  panel.append(buttons);
}
function openClone(backup) {
  if (!requireKey()) return;
  if (pendingCopy()) { renderPending(); $('copy-result').scrollIntoView({ block: 'center', behavior: 'smooth' }); return; }
  state.clone = backup; $('clone-name').textContent = backup.name || 'this backup';
  $('clone-order').value = 'web-' + crypto.randomUUID(); feedback('clone-feedback'); $('clone-dialog').showModal();
}
function showCopy(result) {
  const panel = $('copy-result'); panel.hidden = false; panel.className = 'result-panel';
  panel.replaceChildren(element('h2', '', 'Account copy created'), element('p', '', 'Use these transfer details to receive the copied account. Your backup is unchanged.'));
  const credentials = element('div', 'credentials');
  for (const [label, value] of [['Transfer code', result.transfer_code], ['Confirmation code', result.confirmation_code]]) { const item = element('div'); item.append(element('label', '', label), element('code', '', value)); credentials.append(item); }
  panel.append(credentials, element('p', 'muted', 'Order reference: ' + result.order_id));
  const buttons = element('div', 'result-actions');
  buttons.append(downloadButton('Download transfer details', async () => saveBlob(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }), 'account-copy-' + safeName(result.order_id) + '.json')));
  if (result.recovery_id) buttons.append(downloadButton('Download recovery file', () => downloadPath('/v1/recoveries/' + encodeURIComponent(result.recovery_id) + '/download', 'account-copy.save')));
  panel.append(buttons);
  if (result.persisted === false) panel.append(element('p', '', 'The account was created, but its details could not be saved to history. Download them now.'));
}
async function createCopy() {
  if (state.cloneBusy || !state.clone || !requireKey()) return;
  const order = $('clone-order').value.trim();
  if (!/^[A-Za-z0-9_.:-]{1,100}$/.test(order)) { feedback('clone-feedback', 'Use 1–100 letters, numbers, dots, hyphens or underscores.', 'error'); return; }
  state.cloneBusy = true; $('clone-dialog').querySelectorAll('button').forEach(button => button.disabled = true);
  const pending = { template_id: state.clone.template_id, order_id: order, created_at: new Date().toISOString() };
  storageSet('bcsfe.pending-copy', pending); feedback('clone-feedback', 'Creating account copy…');
  try {
    const result = await api('/v1/templates/' + encodeURIComponent(state.clone.template_id) + '/clones', { method: 'POST', body: { order_id: order } });
    storageSet('bcsfe.pending-copy', null); $('clone-dialog').close(); showCopy(result);
  } catch (error) {
    $('clone-dialog').close();
    if (error.status && error.status < 500 && !error.data.attempt_id) storageSet('bcsfe.pending-copy', null);
    else storageSet('bcsfe.pending-copy', { ...pending, attempt_id: error.data.attempt_id, recovery_id: error.data.recovery_id });
    renderPending(); const panel = $('copy-result'); panel.hidden = false; panel.className = 'result-panel needs-review';
    if (!pendingCopy()) panel.replaceChildren(element('h2', '', 'Copy not created'));
    panel.append(element('p', '', message(error)));
    const buttons = element('div', 'result-actions');
    if (error.data.save_base64) buttons.append(downloadButton('Download available save', async () => saveBlob(blobFromBase64(error.data.save_base64), 'copy-recovery.save')));
    if (error.data.backup_base64) buttons.append(downloadButton('Download original backup', async () => saveBlob(blobFromBase64(error.data.backup_base64), 'original.save')));
    panel.append(buttons);
  } finally { state.cloneBusy = false; $('clone-dialog').querySelectorAll('button').forEach(button => button.disabled = false); }
}
async function loadHistory(append = false) {
  if (!requireKey() || state.historyBusy) return;
  state.historyBusy = true; $('more-history').disabled = true;
  $('refresh-history').disabled = true; feedback('history-feedback', 'Loading copy history…');
  try {
    const page = await api('/v1/template-records?kind=issuance' + (append && state.historyCursor ? '&cursor=' + encodeURIComponent(state.historyCursor) : ''));
    const records = await hydrate((page.records || []).map(item => ({ issuance_id: item.id })), '/v1/issuances/', 'issuance_id');
    if (!append) $('history-list').replaceChildren();
    for (const record of records) {
      const row = element('div', 'history-item'), info = element('div');
      info.append(element('div', '', record.order_id || 'Account copy'), element('div', 'muted', record.load_error || dateLabel(record.created_at))); row.append(info);
      if (record.transfer_code) {
        const show = element('button', 'link-button', 'View transfer details'); show.type = 'button'; show.addEventListener('click', () => showCopy(record)); row.append(show);
        const pending = pendingCopy(); if (pending && pending.order_id === record.order_id && pending.template_id === record.template_id) { storageSet('bcsfe.pending-copy', null); showCopy(record); }
      }
      $('history-list').append(row);
    }
    state.historyCursor = page.next_cursor; $('more-history').hidden = !state.historyCursor;
    feedback('history-feedback', !$('history-list').children.length ? (page.next_cursor ? 'No copies on this page. Load more to continue.' : 'No issued copies yet.') : '');
  } catch (error) { feedback('history-feedback', message(error), 'error'); }
  finally { state.historyBusy = false; $('refresh-history').disabled = false; $('more-history').disabled = false; }
}
function encodeBytes(bytes) { let text = ''; for (let offset = 0; offset < bytes.length; offset += 32768) text += String.fromCharCode(...bytes.subarray(offset, offset + 32768)); return btoa(text); }
async function runEdit(event) {
  event.preventDefault(); if (!requireKey('editor')) return;
  $('editor-result').hidden = true; feedback('editor-feedback');
  try {
    const file = $('editor-file').files[0]; if (!file) throw new Error('Choose a save file first.');
    if (file.size > 1024 * 1024) throw new Error('The save file must be 1 MB or smaller.');
    const operations = JSON.parse($('operations').value); if (!Array.isArray(operations) || !operations.length) throw new Error('Operations must be a nonempty JSON array.');
    $('run-edit').disabled = true; feedback('editor-feedback', 'Applying operations and checking the file…');
    const result = await api('/v2/save/edit', { method: 'POST', kind: 'editor', body: { save_base64: encodeBytes(new Uint8Array(await file.arrayBuffer())), country_code: $('editor-region').value, operations } });
    const panel = $('editor-result'); panel.hidden = false; panel.replaceChildren(element('h2', '', 'Save file ready'), element('p', '', result.change_count + ' saved field' + (result.change_count === 1 ? '' : 's') + ' changed.'));
    const buttons = element('div', 'result-actions');
    buttons.append(downloadButton('Download edited save', async () => saveBlob(blobFromBase64(result.save_base64), safeName(file.name) + '-edited.save')),
      downloadButton('Download original backup', async () => saveBlob(blobFromBase64(result.backup_base64), safeName(file.name) + '-original.save')));
    panel.append(buttons); const details = element('details', 'schema-details'); details.append(element('summary', '', 'View changes'), element('pre', 'editor-diff', JSON.stringify(result.changes, null, 2))); panel.append(details); feedback('editor-feedback');
  } catch (error) { feedback('editor-feedback', message(error), 'error'); }
  finally { $('run-edit').disabled = false; }
}
function typeLabel(schema = {}) {
  if (schema.const !== undefined) return JSON.stringify(schema.const);
  if (schema.enum) return schema.enum.map(value => JSON.stringify(value)).join(' | ');
  if (schema.oneOf || schema.anyOf) return [...new Set((schema.oneOf || schema.anyOf).map(typeLabel))].join(' | ');
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
    row.append(label, element('td', '', typeLabel(value)), element('td', 'parameter-note', notes.join(' '))); body.append(row);
  }
  table.append(body); return table;
}
function sample(schema = {}) {
  if (schema.default !== undefined) return schema.default;
  if (schema.const !== undefined) return schema.const;
  if (schema.enum) return schema.enum[0];
  if (schema.oneOf || schema.anyOf) return sample((schema.oneOf || schema.anyOf)[0]);
  if (schema.type === 'integer' || schema.type === 'number') return schema.minimum ?? 0;
  if (schema.type === 'boolean') return true;
  if (schema.type === 'array') return [sample(schema.items)];
  if (schema.type === 'string') return '';
  return Object.fromEntries((schema.required || []).map(key => [key, sample(schema.properties?.[key])]));
}
function renderReference() {
  const query = $('reference-search').value.trim().toLowerCase(), group = $('action-group').value;
  $('reference-list').replaceChildren(); $('action-group').hidden = state.referenceView !== 'actions';
  const entries = state.referenceView === 'actions' ? Object.entries(state.actions).sort().map(([name, value]) => ({ name, method: 'post', description: value.description, schema: value.schema, source: value.source, action: true })) :
    Object.entries(state.spec?.paths || {}).flatMap(([path, methods]) => Object.entries(methods).filter(([method]) => ['get', 'post', 'delete', 'put', 'patch'].includes(method)).map(([method, value]) => ({ name: path, method, description: value.summary, schema: value.requestBody?.content?.['application/json']?.schema, detail: value.description, action: false })));
  for (const entry of entries) {
    if (!(entry.name + ' ' + entry.description).toLowerCase().includes(query)) continue;
    if (entry.action && group !== 'all' && entry.name.split('.')[0] !== group) continue;
    const details = element('details', 'reference-item'), summary = element('summary');
    if (!entry.action) summary.append(element('span', 'method ' + entry.method, entry.method.toUpperCase()));
    summary.append(element('code', '', entry.name), element('span', 'reference-description', entry.description)); details.append(summary);
    const body = element('div', 'reference-body'); body.append(element('p', '', entry.description));
    if (entry.detail) body.append(element('p', '', entry.detail));
    if (entry.schema) {
      body.append(parameterTable(entry.schema));
      const schema = element('details', 'schema-details'); schema.append(element('summary', '', 'Full JSON schema'), element('pre', '', JSON.stringify(entry.schema, null, 2))); body.append(schema);
    } else body.append(element('p', '', 'No JSON request body.'));
    if (entry.action) {
      const row = element('div', 'section-title'), button = element('button', 'button small', 'Open in editor'); button.type = 'button';
      button.addEventListener('click', () => { $('operations').value = JSON.stringify([{ action: entry.name, args: sample(entry.schema) }], null, 2); location.hash = 'editor'; feedback('editor-feedback', 'Review the arguments for ' + entry.name + ' before applying them.'); }); row.append(button); body.append(row);
    }
    if (entry.source) body.append(element('p', 'source-note', 'Source: ' + entry.source)); details.append(body); $('reference-list').append(details);
  }
  feedback('reference-feedback', $('reference-list').children.length ? '' : 'No matching actions or endpoints.');
}
async function loadReference() {
  try {
    const [features, spec] = await Promise.all([api('/v2/features'), fetch('/openapi.json').then(response => { if (!response.ok) throw new Error('Could not load OpenAPI.'); return response.json(); })]);
    state.actions = features.actions; state.spec = spec; $('action-count').textContent = Object.keys(state.actions).length;
    for (const group of [...new Set(Object.keys(state.actions).map(name => name.split('.')[0]))].sort()) { const option = element('option', '', groupNames[group] || group); option.value = group; $('action-group').append(option); }
    const counts = features.features.counts;
    $('coverage-summary').textContent = counts.source_features + ' source menu features mapped to ' + counts.registered_typed_actions + ' edit actions and file/account endpoints. Device-only and terminal-only operations are listed separately.';
    renderReference();
  } catch (error) { feedback('reference-feedback', message(error), 'error'); }
}

window.addEventListener('hashchange', navigate);
$('mobile-page').addEventListener('change', event => location.hash = event.target.value);
for (const id of ['authorize', 'connect-library', 'connect-overview']) $(id).addEventListener('click', openAuth);
document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => { if (button.dataset.close !== 'clone-dialog' || !state.cloneBusy) $(button.dataset.close).close(); }));
$('clone-dialog').addEventListener('cancel', event => { if (state.cloneBusy) event.preventDefault(); });
$('auth-form').addEventListener('submit', async event => {
  event.preventDefault(); const old = { key: state.key, editorKey: state.editorKey };
  state.key = $('api-key').value.trim(); state.editorKey = $('editor-key').value.trim();
  if (!state.key && !state.editorKey) { feedback('auth-feedback', 'Enter an API key.', 'error'); return; }
  $('connect-submit').disabled = true; feedback('auth-feedback', 'Connecting…');
  const [backups, editor] = await Promise.allSettled([api('/v1/templates'), api('/v2/editor/config', { kind: 'editor' })]);
  if (backups.status === 'fulfilled' || editor.status === 'fulfilled') {
    storageSet('bcsfe.api-keys', $('remember-key').checked ? { key: state.key, editorKey: state.editorKey } : null);
    updateConnection(); $('auth-dialog').close();
    if (backups.status === 'fulfilled') await loadBackups(false, backups.value);
    else { renderBackups(); feedback('library-feedback', message(backups.reason), 'error'); }
  } else { Object.assign(state, old); feedback('auth-feedback', message(backups.reason), 'error'); }
  $('connect-submit').disabled = false;
});
$('disconnect').addEventListener('click', () => { state.key = ''; state.editorKey = ''; state.backups.clear(); state.backupCursor = null; storageSet('bcsfe.api-keys', null); updateConnection(); renderBackups(); $('auth-dialog').close(); $('copy-result').hidden = true; $('editor-result').hidden = true; $('history-list').replaceChildren(); feedback('library-feedback'); });
$('backup-file').addEventListener('change', setFileLabel);
for (const event of ['dragenter', 'dragover']) $('backup-drop').addEventListener(event, e => { e.preventDefault(); $('backup-drop').classList.add('dragging'); });
for (const event of ['dragleave', 'drop']) $('backup-drop').addEventListener(event, e => { e.preventDefault(); $('backup-drop').classList.remove('dragging'); });
$('backup-drop').addEventListener('drop', event => { if (event.dataTransfer.files.length) { $('backup-file').files = event.dataTransfer.files; setFileLabel(); } });
$('backup-form').addEventListener('submit', saveBackup);
$('local-backup').addEventListener('click', () => { try { const file = selectedBackupFile(); saveBlob(file, safeName(file.name) + '-backup.save'); feedback('backup-feedback', 'Local copy downloaded.', 'success'); } catch (error) { feedback('backup-feedback', error.message, 'error'); } });
$('refresh-backups').addEventListener('click', () => requireKey() && loadBackups());
$('more-backups').addEventListener('click', () => loadBackups(true));
$('confirm-clone').addEventListener('click', createCopy);
$('refresh-history').addEventListener('click', () => loadHistory());
$('more-history').addEventListener('click', () => loadHistory(true));
$('copy-history').addEventListener('toggle', () => { if ($('copy-history').open && !$('history-list').children.length && state.key) loadHistory(); });
$('editor-form').addEventListener('submit', runEdit);
$('reference-search').addEventListener('input', renderReference); $('action-group').addEventListener('change', renderReference);
for (const view of ['actions', 'endpoints']) $('show-' + view).addEventListener('click', () => { state.referenceView = view; $('show-actions').classList.toggle('selected', view === 'actions'); $('show-endpoints').classList.toggle('selected', view === 'endpoints'); renderReference(); });
document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => { try { await navigator.clipboard.writeText($(button.dataset.copy).textContent); button.textContent = 'Copied'; } catch { button.textContent = 'Select code to copy'; } }));
const remembered = storageGet('bcsfe.api-keys'); if (remembered && typeof remembered.key === 'string') { state.key = remembered.key; state.editorKey = remembered.editorKey || ''; $('remember-key').checked = true; }
navigate(); updateConnection(); renderBackups(); renderPending(); loadReference(); if (state.key) loadBackups();

"""Use on a persistent vending backend, never Vercel's temporary filesystem.

One durable SQLite order database must be shared by every worker using this helper.
For multiple machines, use your existing transactional order database instead.
"""
from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path
import requests

class OrderNeedsAttention(RuntimeError):
    pass

@contextmanager
def order_database(path):
    db = sqlite3.connect(path, timeout=15)
    try:
        with db:
            yield db
    finally:
        db.close()

def issue_once(api_url, token, template_id, order_id, db_path, session=None):
    if str(db_path) == ':memory:':
        raise ValueError('A durable order database is required.')
    Path(db_path).resolve().parent.mkdir(parents=True, exist_ok=True)
    with order_database(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS template_orders '
                   '(order_id TEXT PRIMARY KEY, template_id TEXT NOT NULL, status TEXT NOT NULL, result TEXT)')
        inserted = db.execute('INSERT OR IGNORE INTO template_orders VALUES (?, ?, ?, NULL)',
                              (order_id, template_id, 'pending')).rowcount
        if not inserted:
            saved_template, status, result = db.execute(
                'SELECT template_id, status, result FROM template_orders WHERE order_id=?', (order_id,)).fetchone()
            if saved_template != template_id:
                raise ValueError('This order already belongs to a different template.')
            if status == 'issued':
                return json.loads(result)
            raise OrderNeedsAttention('Order is pending or uncertain; inspect it without issuing again.')
    # The unique order reservation is committed before the external side effect.
    client = session or requests
    try:
        response = client.post(api_url.rstrip('/') + '/v1/templates/' + template_id + '/clones',
                               json={'order_id': order_id},
                               headers={'Authorization': 'Bearer ' + token},
                               timeout=(5, 180), allow_redirects=False)
        result = response.json()
        success = (response.status_code == 201 and isinstance(result, dict)
                   and result.get('success') is True and result.get('status') == 'issued'
                   and bool(result.get('transfer_code')) and bool(result.get('confirmation_code')))
    except (requests.RequestException, ValueError):
        result = {'success': False, 'message': 'Response uncertain. Inspect API records before further action.'}
        success = False
    with order_database(db_path) as db:
        db.execute('UPDATE template_orders SET status=?, result=? WHERE order_id=?',
                   ('issued' if success else 'needs_attention', json.dumps(result), order_id))
    if not success:
        raise OrderNeedsAttention('Issuance needs attention. The response was saved in the order database.')
    return result

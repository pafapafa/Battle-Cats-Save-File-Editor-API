const API_URL = 'https://battle-cats-save-file-editor-api.vercel.app/edit';

async function editSave() {
    const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            transfer_code: '1a2b3c4d5',
            confirmation_code: '1234',
            country_code: 'kr',
            catfood: 45000,
            unlock_cats: true,
            max_treasures: true
        })
    });

    const data = await response.json();

    if (data.success) {
        console.log('Transfer Code:', data.transfer_code);
        console.log('Confirmation PIN:', data.confirmation_code);
    } else {
        console.error('Error:', data.message);
    }
}

editSave();

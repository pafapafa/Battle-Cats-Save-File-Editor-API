interface EditRequest {
  transfer_code: string;
  confirmation_code: string;
  country_code: string;
  catfood?: number;
  unlock_cats?: boolean;
}

interface EditResponse {
  success: boolean;
  message: string;
  transfer_code?: string;
  confirmation_code?: string;
}

async function run(): Promise<void> {
  const payload: EditRequest = {
    transfer_code: "1a2b3c4d5",
    confirmation_code: "1234",
    country_code: "kr",
    catfood: 45000,
    unlock_cats: true
  };

  const response = await fetch("https://battle-cats-save-file-editor-api.vercel.app/edit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const data: EditResponse = await response.json();
  console.log("Success:", data.success);
  console.log("Transfer Code:", data.transfer_code);
}

run();

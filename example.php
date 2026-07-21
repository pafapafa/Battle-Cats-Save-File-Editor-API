<?php

$url = "https://battle-cats-save-file-editor-api.vercel.app/edit";
$data = [
    "transfer_code" => "1a2b3c4d5",
    "confirmation_code" => "1234",
    "country_code" => "kr",
    "catfood" => 45000,
    "unlock_cats" => true
];

$options = [
    "http" => [
        "header"  => "Content-Type: application/json\r\n",
        "method"  => "POST",
        "content" => json_encode($data)
    ]
];

$context  = stream_context_create($options);
$result = file_get_contents($url, false, $context);

echo "Response:\n" . $result . "\n";
?>

#!/usr/bin/env bash

curl -X POST "https://battle-cats-save-file-editor-api.vercel.app/edit" \
     -H "Content-Type: application/json" \
     -d '{
           "transfer_code": "1a2b3c4d5",
           "confirmation_code": "1234",
           "country_code": "kr",
           "catfood": 45000,
           "unlock_cats": true,
           "max_treasures": true
         }'

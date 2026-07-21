package main

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"time"
)

func main() {
	url := "https://battle-cats-save-file-editor-api.vercel.app/edit"
	payload := []byte(`{
		"transfer_code": "1a2b3c4d5",
		"confirmation_code": "1234",
		"country_code": "kr",
		"catfood": 45000,
		"unlock_cats": true,
		"max_treasures": true
	}`)

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(payload))
	if err != nil {
		fmt.Println("Error creating request:", err)
		return
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 45 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Println("Error sending request:", err)
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	fmt.Println("Response Status:", resp.Status)
	fmt.Println("Response Body:\n", string(body))
}

package main

import (
	"bytes"
	"fmt"
	"io"
	"mime"
	"net"
	"net/http"
	"os"
	"strings"
	"time"
)

const limit = 2 * 1024 * 1024

func setting(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

func run(args []string) error {
	if len(args) != 2 {
		return fmt.Errorf("usage: example REQUEST_JSON OUTPUT_SAVE")
	}
	key := setting("EDITOR_API_KEY", os.Getenv("TEMPLATE_API_KEY"))
	if key == "" {
		return fmt.Errorf("set EDITOR_API_KEY or TEMPLATE_API_KEY")
	}
	if _, err := os.Lstat(args[1]); err == nil {
		return fmt.Errorf("output already exists; choose a new path")
	} else if !os.IsNotExist(err) {
		return err
	}
	info, err := os.Stat(args[0])
	if err != nil {
		return err
	}
	if info.Size() == 0 || info.Size() > limit {
		return fmt.Errorf("request must be 1 byte to 2 MiB")
	}
	payload, err := os.ReadFile(args[0])
	if err != nil {
		return err
	}
	url := strings.TrimRight(setting("BCSFE_API_URL", "https://battle-cats-save-file-editor-api.vercel.app"), "/") + "/v2/save/edit"
	request, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(payload))
	if err != nil {
		return err
	}
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("Accept", "application/octet-stream")
	request.Header.Set("Authorization", "Bearer "+key)
	transport := &http.Transport{
		Proxy:                 http.ProxyFromEnvironment,
		DialContext:           (&net.Dialer{Timeout: 15 * time.Second}).DialContext,
		TLSHandshakeTimeout:   15 * time.Second,
		ResponseHeaderTimeout: 120 * time.Second,
	}
	defer transport.CloseIdleConnections()
	client := &http.Client{
		Timeout:   120 * time.Second,
		Transport: transport,
		CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
	response, err := client.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return fmt.Errorf("API returned HTTP %d; no save was written", response.StatusCode)
	}
	contentType, _, err := mime.ParseMediaType(response.Header.Get("Content-Type"))
	if err != nil || contentType != "application/octet-stream" {
		return fmt.Errorf("expected a binary save; set output to file in the request JSON")
	}
	save, err := io.ReadAll(io.LimitReader(response.Body, limit+1))
	if err != nil {
		return err
	}
	if len(save) == 0 || len(save) > limit {
		return fmt.Errorf("response is empty or exceeds 2 MiB")
	}
	output, err := os.OpenFile(args[1], os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return err
	}
	count, writeError := output.Write(save)
	closeError := output.Close()
	if writeError != nil || closeError != nil || count != len(save) {
		os.Remove(args[1])
		if writeError != nil {
			return writeError
		}
		if closeError != nil {
			return closeError
		}
		return io.ErrShortWrite
	}
	fmt.Printf("Saved %d bytes to %s\n", len(save), args[1])
	return nil
}

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
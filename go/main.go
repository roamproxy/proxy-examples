// Rotating and sticky RoamProxy sessions with Go's net/http.
//
//   go run main.go
//
// Set ROAM_USER and ROAM_PASS in your environment first.
package main

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"time"
)

const gateway = "gw.roamproxy.com:41080"

func client(username string) *http.Client {
	pass := os.Getenv("ROAM_PASS")
	proxyURL, _ := url.Parse(fmt.Sprintf("http://%s:%s@%s", username, pass, gateway))
	return &http.Client{
		Transport: &http.Transport{Proxy: http.ProxyURL(proxyURL)},
		Timeout:   30 * time.Second,
	}
}

func getIP(username string) (string, error) {
	resp, err := client(username).Get("https://ipinfo.io/ip")
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	return string(body), err
}

func main() {
	user := os.Getenv("ROAM_USER")

	// Fresh rotating IP each call.
	ip, _ := getIP(user + "-country-us")
	fmt.Println("rotating:", ip)

	// Sticky IP: reuse the session id to keep the same exit.
	sticky := user + "-country-fr-session-demo42"
	ip, _ = getIP(sticky)
	fmt.Println("sticky:  ", ip)
	ip, _ = getIP(sticky)
	fmt.Println("sticky:  ", ip)
}

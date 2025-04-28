package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"math"
	"net/http"
	"time"
)

// IQData represents a single IQ data point
type IQData struct {
	Time      float64 `json:"time"`
	Real      float64 `json:"real"`
	Imaginary float64 `json:"imaginary"`
}

// generateIQData creates fake IQ data points using sine waves
func generateIQData(count int, startTime float64) []IQData {
	data := make([]IQData, count)
	
	for i := 0; i < count; i++ {
		t := startTime + float64(i)*0.1
		
		// Generate real component using sine wave
		real := math.Sin(t)
		
		// Generate imaginary component using cosine wave
		imaginary := math.Cos(t)
		
		data[i] = IQData{
			Time:      t,
			Real:      real,
			Imaginary: imaginary,
		}
	}
	
	return data
}

// sendToWebhook sends the IQ data to the specified webhook URL
func sendToWebhook(data []IQData, webhookURL string) error {
	// Marshal the data to JSON
	jsonData, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("error marshaling JSON: %v", err)
	}
	
	// Create the HTTP request
	req, err := http.NewRequest("POST", webhookURL, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("error creating request: %v", err)
	}
	
	// Set headers
	req.Header.Set("Content-Type", "application/json")
	
	// Send the request
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("error sending request: %v", err)
	}
	defer resp.Body.Close()
	
	// Check response status
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("unexpected response status: %s", resp.Status)
	}
	
	log.Printf("Successfully sent %d IQ data points to webhook", len(data))
	return nil
}

func main() {
	// Define command line flags
	webhookURL := flag.String("webhook", "http://localhost:7070/webhook", "URL of the webhook receiver")
	dataPoints := flag.Int("points", 10, "Number of data points to generate per second")
	intervalMs := flag.Int("interval", 1000, "Interval between data sends in milliseconds")
	flag.Parse()
	
	log.Printf("Starting IQ data generator")
	log.Printf("Webhook URL: %s", *webhookURL)
	log.Printf("Data points per send: %d", *dataPoints)
	log.Printf("Interval: %d ms", *intervalMs)
	
	// Keep track of the time for continuous data generation
	var currentTime float64 = 0.0
	
	// Infinite loop to generate and send data
	for {
		// Generate fake IQ data
		data := generateIQData(*dataPoints, currentTime)
		
		// Update the current time for the next batch
		currentTime += float64(*dataPoints) * 0.1
		
		// Send data to webhook
		err := sendToWebhook(data, *webhookURL)
		if err != nil {
			log.Printf("Error sending data: %v", err)
		}
		
		// Wait before sending the next batch
		time.Sleep(time.Duration(*intervalMs) * time.Millisecond)
	}
}

package main

import (
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
)

// IQData represents a single IQ data point
type IQData struct {
	Time      float64 `json:"time"`
	Real      float64 `json:"real"`
	Imaginary float64 `json:"imaginary"`
}

// Global in-memory storage for IQ data
var iqStore = []IQData{}

// Maximum number of data points to store
const maxDataPoints = 1000

func main() {
	// Initialize Gin router
	r := gin.Default()

	// Enable CORS for frontend access
	r.Use(func(c *gin.Context) {
    c.Writer.Header().Set("Access-Control-Allow-Origin", "http://localhost:5173")
    c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
    c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}
		c.Next()
	})

	// Webhook endpoint to receive IQ data
	r.POST("/webhook", func(c *gin.Context) {
		var newData []IQData

		// Parse the incoming JSON data
		if err := c.ShouldBindJSON(&newData); err != nil {
			log.Printf("Error parsing JSON: %v", err)
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid JSON format"})
			return
		}

		// Log the received data
		log.Printf("Received %d IQ data points", len(newData))

		// Append new data to the store
		iqStore = append(iqStore, newData...)

		// Trim the store if it exceeds the maximum size
		if len(iqStore) > maxDataPoints {
			iqStore = iqStore[len(iqStore)-maxDataPoints:]
		}

		// Return success response
		c.JSON(http.StatusOK, gin.H{"status": "received"})
	})

	// API endpoint to serve stored IQ data
	r.GET("/api/iq-data", func(c *gin.Context) {
		c.JSON(http.StatusOK, iqStore)
	})

	// Static file server for the frontend (optional, uncomment if needed)
	// r.Static("/", "./public")

	// Start the server
	log.Println("Starting IQ Data server on port 7070...")
	if err := r.Run(":7070"); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}

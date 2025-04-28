<script>
  import { onMount } from 'svelte';
  
  // Track connection status
  let isConnected = false;
  let statusMessage = 'Connecting to server...';
  
  // Check server connection on mount
  onMount(async () => {
    try {
      const response = await fetch('localhost:7070/api/iq-data');
      if (response.ok) {
        isConnected = true;
        statusMessage = 'Connected to server';
      } else {
        statusMessage = 'Error connecting to server';
      }
    } catch (error) {
      statusMessage = 'Server unavailable';
    }
  });
</script>

<div class="app">
  
  <slot></slot>
</div>

<style>
  .app {
    width: 100%;
    height: 100vh;
    position: relative;
    font-family: Arial, sans-serif;
  }
  
  .status-bar {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    background-color: rgba(0, 0, 0, 0.7);
    color: #ff5555;
    padding: 0.5rem 1rem;
    display: flex;
    align-items: center;
    z-index: 1000;
  }
  
  .status-bar.connected {
    color: #55ff55;
  }
  
  .status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background-color: #ff5555;
    margin-right: 0.5rem;
  }
  
  .status-bar.connected .status-dot {
    background-color: #55ff55;
  }
  
  .status-text {
    font-size: 0.9rem;
  }
  
  :global(body) {
    margin: 0;
    padding: 0;
    overflow: hidden;
    background-color: #1a1a1a;
  }
</style>

<script>
  import { onMount, onDestroy } from 'svelte';
  import * as THREE from 'three';
  import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
  
  // Data store for IQ values
  let iqData = [];
  
  // Three.js components
  let container;
  let scene, camera, renderer, controls;
  let dataLine;
  let animationId;
  
  // Status tracking
  let useTestData = false;
  let statusMessage = "Connecting to server...";
  
  // Initialize the scene
  function initScene() {
    // Create the scene
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a1a);
    
    // Create camera
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.set(30, 30, 100);
    camera.lookAt(0, 0, 0);
    
    // Create renderer
    renderer = new THREE.WebGLRenderer({ antialias: true, canvas: container });
    renderer.setSize(window.innerWidth, window.innerHeight);
    
    // Add orbit controls for interaction
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    
    // Add axes
    createAxes();
    
    // Add initial empty line for the data
    createDataLine();
    
    // Handle window resize
    window.addEventListener('resize', onWindowResize);
  }
  
  // Create the three axes with labels
  function createAxes() {
    // Axis lengths
    const axisLength = 50;
    
    // Materials for each axis
    const xAxisMaterial = new THREE.LineBasicMaterial({ color: 0xff0000 }); // Red for X (Time)
    const yAxisMaterial = new THREE.LineBasicMaterial({ color: 0x00ff00 }); // Green for Y (Real)
    const zAxisMaterial = new THREE.LineBasicMaterial({ color: 0x0000ff }); // Blue for Z (Imaginary)
    
    // Create geometries for the axes
    const xAxisGeometry = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-axisLength, 0, 0),
      new THREE.Vector3(axisLength, 0, 0)
    ]);
    
    const yAxisGeometry = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, -axisLength, 0),
      new THREE.Vector3(0, axisLength, 0)
    ]);
    
    const zAxisGeometry = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 0, -axisLength),
      new THREE.Vector3(0, 0, axisLength)
    ]);
    
    // Create the axis lines
    const xAxis = new THREE.Line(xAxisGeometry, xAxisMaterial);
    const yAxis = new THREE.Line(yAxisGeometry, yAxisMaterial);
    const zAxis = new THREE.Line(zAxisGeometry, zAxisMaterial);
    
    // Add axes to the scene
    scene.add(xAxis);
    scene.add(yAxis);
    scene.add(zAxis);
    
    // Create axis labels
    createAxisLabel("Time", axisLength + 5, 0, 0, 0xff0000);
    createAxisLabel("Real", 0, axisLength + 5, 0, 0x00ff00);
    createAxisLabel("Imaginary", 0, 0, axisLength + 5, 0x0000ff);
  }
  
  // Create text labels for the axes
  function createAxisLabel(text, x, y, z, color) {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    canvas.width = 128;
    canvas.height = 64;
    
    context.fillStyle = `rgba(0, 0, 0, 0)`;
    context.fillRect(0, 0, canvas.width, canvas.height);
    
    context.font = '24px Arial';
    context.fillStyle = `#${color.toString(16).padStart(6, '0')}`;
    context.textAlign = 'center';
    context.fillText(text, canvas.width / 2, canvas.height / 2);
    
    const texture = new THREE.CanvasTexture(canvas);
    const material = new THREE.SpriteMaterial({ map: texture });
    const sprite = new THREE.Sprite(material);
    
    sprite.position.set(x, y, z);
    sprite.scale.set(10, 5, 1);
    scene.add(sprite);
  }
  
  // Create the data line
  function createDataLine() {
    const geometry = new THREE.BufferGeometry();
    const material = new THREE.LineBasicMaterial({ color: 0xffff00 }); // Yellow for the data line
    
    if (dataLine) {
      scene.remove(dataLine);
    }
    
    dataLine = new THREE.Line(geometry, material);
    scene.add(dataLine);
  }
  
  // Update the data line with new IQ data
  function updateGraph() {
    if (!dataLine || iqData.length < 2) return;
    
    // Create points array from the IQ data
    const points = [];
    for (let i = 0; i < iqData.length; i++) {
      const point = iqData[i];
      points.push(new THREE.Vector3(point.time, point.real, point.imaginary));
    }
    
    // Update the line geometry
    dataLine.geometry.dispose();
    dataLine.geometry = new THREE.BufferGeometry().setFromPoints(points);
  }
  
  // Animation loop
  function animate() {
    animationId = requestAnimationFrame(animate);
    
    controls.update();
    renderer.render(scene, camera);
  }
  
  // Handle window resize
  function onWindowResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }
  
  // Generate test data for development
  function generateTestData() {
    // Time counter for continuous data generation
    let timeCounter = iqData.length > 0 ? iqData[iqData.length - 1].time + 0.5 : 0;
    
    // Generate new test data
    const testData = [];
    const numPoints = 10; // Add 10 points at a time
    
    for (let i = 0; i < numPoints; i++) {
      const time = timeCounter + i * 0.5;
      testData.push({
        time: time,
        real: Math.sin(time * 0.1) * 10,
        imaginary: Math.cos(time * 0.1) * 10
      });
    }
    
    // Add new data to existing data, keeping last 100 points
    iqData = [...iqData, ...testData].slice(-100);
    updateGraph();
  }
  
  // Fetch IQ data from the server
  async function fetchData() {
    if (useTestData) {
      generateTestData();
      return;
    }
    
    try {
      const response = await fetch('http://localhost:7070/api/iq-data');
      if (response.ok) {
        const data = await response.json();
        iqData = data;
        updateGraph();
        statusMessage = "Connected to server - using real data";
      } else {
        console.log(response)
        // If API returns an error, switch to test data
        console.warn('API returned error, switching to test data mode');
        useTestData = true;
        statusMessage = "Server error - using simulated data";
        generateTestData();
      }
    } catch (error) {
      // If API is unavailable, switch to test data
      console.warn('API unavailable, switching to test data mode:', error);
      useTestData = true;
      statusMessage = "Server unavailable - using simulated data";
      generateTestData();
    }
  }
  
  // Set up polling for data
  let fetchInterval;
  
  onMount(() => {
    initScene();
    animate();
    
    // Initial data fetch to determine if we need test data
    fetchData();
    
    // Poll for new data every second
    fetchInterval = setInterval(fetchData, 1000);
  });
 
/*
  onDestroy(() => {
    clearInterval(fetchInterval);
    window.removeEventListener('resize', onWindowResize);
    
    if (animationId) {
      cancelAnimationFrame(animationId);
    }
    
    if (renderer) {
      renderer.dispose();
    }
  });
*/
</script>

<canvas bind:this={container}></canvas>

<div class="status-indicator" class:test-mode={useTestData}>
  <span class="status-dot"></span>
  <span class="status-text">{statusMessage}</span>
</div>

<style>
  canvas {
    width: 100%;
    height: 100%;
    display: block;
  }
  
  .status-indicator {
    position: absolute;
    bottom: 10px;
    left: 10px;
    background-color: rgba(0, 0, 0, 0.7);
    color: #4CAF50;
    padding: 5px 10px;
    border-radius: 4px;
    display: flex;
    align-items: center;
    font-family: Arial, sans-serif;
    font-size: 14px;
    z-index: 100;
  }
  
  .status-indicator.test-mode {
    color: #FFC107;
  }
  
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #4CAF50;
    margin-right: 8px;
  }
  
  .status-indicator.test-mode .status-dot {
    background-color: #FFC107;
  }
  
  :global(body) {
    margin: 0;
    padding: 0;
    overflow: hidden;
  }
</style>

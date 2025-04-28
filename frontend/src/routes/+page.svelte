<script>
  import IQGraph from '$lib/IQGraph.svelte';
</script>

<div class="container">
  <header>
    <h1>Real-Time IQ Data Visualization</h1>
  </header>
  
  <div class="visualization">
    <IQGraph />
  </div>
</div>

<style>
  .container {
    width: 100%;
    height: 100vh;
    display: flex;
    flex-direction: column;
    background-color: #1a1a1a;
    color: white;
  }
  
  header {
    padding: 1rem;
    text-align: center;
    background-color: rgba(0, 0, 0, 0.5);
    z-index: 10;
    position: absolute;
    width: 100%;
    box-sizing: border-box;
  }
  
  h1 {
    margin: 0;
    font-size: 1.5rem;
  }
  
  .visualization {
    flex: 1;
    position: relative;
  }
</style>

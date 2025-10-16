import { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [endpoint, setEndpoint] = useState('');

  useEffect(() => {
    chrome.storage.local.get(['llmEndpoint'], (result) => {
      if (result.llmEndpoint) {
        setEndpoint(result.llmEndpoint);
      }
    });
  }, []);

  const handleSave = () => {
    chrome.storage.local.set({ llmEndpoint: endpoint }, () => {
      alert('Endpoint saved!');
    });
  };

  return (
    <div className="App">
      <h1>LLM Translator Settings</h1>
      <div className="card">
        <label htmlFor="endpoint">LLM Endpoint URL:</label>
        <input
          id="endpoint"
          type="text"
          value={endpoint}
          onChange={(e) => setEndpoint(e.target.value)}
          style={{ width: '300px', marginLeft: '10px' }}
        />
        <button onClick={handleSave} style={{ marginLeft: '10px' }}>
          Save
        </button>
      </div>
    </div>
  );
}

export default App;

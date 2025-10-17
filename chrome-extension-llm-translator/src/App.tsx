import { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [endpoint, setEndpoint] = useState('');
  const [status, setStatus] = useState('');

  // Load the saved endpoint from chrome.storage when the component mounts
  useEffect(() => {
    chrome.storage.local.get(['llmEndpoint'], (result) => {
      if (chrome.runtime.lastError) {
        console.error(chrome.runtime.lastError);
        setStatus('Error loading settings.');
      } else if (result.llmEndpoint) {
        setEndpoint(result.llmEndpoint);
      }
    });
  }, []);

  // Save the endpoint to chrome.storage
  const handleSave = () => {
    setStatus('Saving...');
    chrome.storage.local.set({ llmEndpoint: endpoint }, () => {
      if (chrome.runtime.lastError) {
        console.error(chrome.runtime.lastError);
        setStatus('Error saving settings.');
      } else {
        setStatus('Endpoint saved successfully!');
        setTimeout(() => setStatus(''), 2000); // Clear status message after 2 seconds
      }
    });
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>LLM Translator Settings</h1>
        <p>Configure the endpoint for your local LLM.</p>
      </header>
      <main>
        <div className="form-group">
          <label htmlFor="endpoint-input">LLM Endpoint URL:</label>
          <input
            id="endpoint-input"
            type="url"
            value={endpoint}
            onChange={(e) => setEndpoint(e.target.value)}
            placeholder="e.g., http://localhost:11434/v1/chat/completions"
          />
        </div>
        <button onClick={handleSave}>Save</button>
        {status && <p className="status-message">{status}</p>}
      </main>
    </div>
  );
}

export default App;

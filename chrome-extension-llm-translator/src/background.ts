// src/background.ts

chrome.runtime.onMessage.addListener((request, sender) => {
  if (request.type === 'translate') {
    (async () => {
      const { llmEndpoint } = await chrome.storage.local.get('llmEndpoint');
      const tabId = sender.tab?.id;

      if (!llmEndpoint) {
        console.error('LLM endpoint is not set.');
        if (tabId) {
          chrome.tabs.sendMessage(tabId, {
            type: 'translationError',
            error: 'LLM endpoint is not set. Please set it in the options page.',
          });
        }
        return;
      }

      try {
        const response = await fetch(llmEndpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            // Note: This model may need to be configurable in the future
            model: "gemma:2b",
            messages: [{
              role: "user",
              content: `Translate the following English text to Japanese, outputting only the translated text: ${request.text}`
            }],
            stream: true,
          }),
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        if (!response.body) {
          throw new Error('Response body is null');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        const processStream = async () => {
          while (true) {
            const { done, value } = await reader.read();
            if (done) {
              if (tabId) {
                chrome.tabs.sendMessage(tabId, { type: 'translationComplete' });
              }
              break;
            }

            const chunk = decoder.decode(value, { stream: true });
            // OpenAI/Ollama stream chunks are prefixed with "data: "
            const lines = chunk.split('\n').filter(line => line.startsWith('data: '));

            for (const line of lines) {
              const jsonStr = line.replace('data: ', '');
              if (jsonStr === '[DONE]') continue;

              try {
                const parsed = JSON.parse(jsonStr);
                const delta = parsed.choices[0]?.delta?.content;

                if (delta && tabId) {
                  chrome.tabs.sendMessage(tabId, {
                    type: 'translationStream',
                    delta: delta,
                  });
                }
              } catch (error) {
                console.error('Error parsing stream chunk:', jsonStr, error);
              }
            }
          }
        };
        processStream();

      } catch (error) {
        console.error('Error fetching from LLM:', error);
        if (tabId) {
          const errorMessage = error instanceof Error ? error.message : String(error);
          chrome.tabs.sendMessage(tabId, {
            type: 'translationError',
            error: `Failed to fetch from LLM: ${errorMessage}`,
          });
        }
      }
    })();

    // Return true to indicate that we will send a response asynchronously.
    return true;
  }
});

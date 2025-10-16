// src/background.ts

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'translate') {
    (async () => {
      const { llmEndpoint } = await chrome.storage.local.get('llmEndpoint');

      if (!llmEndpoint) {
        console.error('LLM endpoint is not set.');
        // It's tricky to send an async error back with sendResponse,
        // so we'll send a message back to the tab.
        if (sender.tab?.id) {
          chrome.tabs.sendMessage(sender.tab.id, {
            type: 'translationError',
            error: 'LLM endpoint is not set.',
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
            model: "gpt-4", // This will be customized later
            messages: [{
              role: "user",
              content: `Translate the following text to Japanese: ${request.text}`
            }],
            stream: true,
          }),
        });

        if (!response.body) {
          throw new Error('Response body is null');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }

          const chunk = decoder.decode(value, { stream: true });
          // OpenAI stream chunks are prefixed with "data: "
          const lines = chunk.split('\n').filter(line => line.startsWith('data: '));

          for (const line of lines) {
            const jsonStr = line.replace('data: ', '');
            if (jsonStr === '[DONE]') {
              if (sender.tab?.id) {
                chrome.tabs.sendMessage(sender.tab.id, { type: 'translationComplete' });
              }
              continue;
            }
            try {
              const parsed = JSON.parse(jsonStr);
              const delta = parsed.choices[0]?.delta?.content;
              if (delta && sender.tab?.id) {
                chrome.tabs.sendMessage(sender.tab.id, {
                  type: 'translationStream',
                  delta: delta,
                });
              }
            } catch (error) {
              console.error('Error parsing stream chunk:', error);
            }
          }
        }
      } catch (error) {
        console.error('Error fetching from LLM:', error);
        if (sender.tab?.id) {
          chrome.tabs.sendMessage(sender.tab.id, {
            type: 'translationError',
            error: `Error fetching from LLM: ${error.message}`,
          });
        }
      }
    })();

    // Return true to indicate that we will send a response asynchronously.
    return true;
  }
});

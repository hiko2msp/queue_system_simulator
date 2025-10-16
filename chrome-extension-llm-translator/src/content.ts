// src/content.ts

let originalTexts = new Map<Node, string>();
let currentlyTranslatingNode: Node | null = null;
let textNodes: Node[] = [];
let textNodeIndex = 0;

function collectTextNodes(root: Node) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node: Text) => {
      // Ignore empty/whitespace-only text nodes and script/style content
      if (node.nodeValue?.trim() && !node.parentElement?.closest('script, style')) {
        return NodeFilter.FILTER_ACCEPT;
      }
      return NodeFilter.FILTER_REJECT;
    }
  });

  const nodes: Node[] = [];
  while(walker.nextNode()) {
    nodes.push(walker.currentNode);
  }
  return nodes;
}

function startTranslation() {
  textNodes = collectTextNodes(document.body);
  translateNextNode();
}

function translateNextNode() {
  if (textNodeIndex >= textNodes.length) {
    console.log('All text nodes translated.');
    return;
  }

  const node = textNodes[textNodeIndex];
  if (node.nodeValue) {
    currentlyTranslatingNode = node;
    originalTexts.set(node, node.nodeValue); // Save original text
    node.nodeValue = '...'; // Placeholder for translation
    chrome.runtime.sendMessage({ type: 'translate', text: originalTexts.get(node) });
  } else {
    // Skip node if it has no value and move to the next one
    textNodeIndex++;
    translateNextNode();
  }
}

chrome.runtime.onMessage.addListener((request) => {
  if (currentlyTranslatingNode) {
    if (request.type === 'translationStream') {
      if (currentlyTranslatingNode.nodeValue === '...') {
        currentlyTranslatingNode.nodeValue = ''; // Clear placeholder on first chunk
      }
      currentlyTranslatingNode.nodeValue += request.delta;
    } else if (request.type === 'translationComplete') {
      currentlyTranslatingNode = null;
      textNodeIndex++;
      translateNextNode(); // Move to the next node
    } else if (request.type === 'translationError') {
      console.error('Translation Error:', request.error);
      // Restore original text on error
      if (originalTexts.has(currentlyTranslatingNode)) {
        currentlyTranslatingNode.nodeValue = originalTexts.get(currentlyTranslatingNode) ?? '';
      }
      currentlyTranslatingNode = null;
      textNodeIndex++;
      translateNextNode();
    }
  }
});

// Start the translation process once the page is fully loaded.
window.addEventListener('load', () => {
  // A small delay to ensure all dynamic content is loaded.
  setTimeout(startTranslation, 1000);
});

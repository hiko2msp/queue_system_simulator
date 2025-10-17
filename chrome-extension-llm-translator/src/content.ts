// src/content.ts

// A Map to store original text content of nodes before translation
const originalTexts = new Map<Node, string>();
// A queue of text nodes to be translated
let textNodesToTranslate: Node[] = [];
// Index to keep track of the current node being processed
let currentNodeIndex = 0;
// The node currently being translated
let activeTranslatingNode: Node | null = null;

/**
 * Traverses the DOM from a given root element and collects all non-empty text nodes
 * that are not inside <script> or <style> tags.
 * @param root The root element to start traversal from.
 * @returns An array of text nodes.
 */
function collectTextNodes(root: Node): Node[] {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node: Text) => {
      // Ignore empty/whitespace-only text nodes and content of script/style tags
      if (node.nodeValue?.trim() && !node.parentElement?.closest('script, style, textarea')) {
        return NodeFilter.FILTER_ACCEPT;
      }
      return NodeFilter.FILTER_REJECT;
    }
  });

  const nodes: Node[] = [];
  while (walker.nextNode()) {
    nodes.push(walker.currentNode);
  }
  return nodes;
}

/**
 * Kicks off the translation for the next node in the queue.
 */
function translateNextNode() {
  if (currentNodeIndex >= textNodesToTranslate.length) {
    console.log('All text nodes have been processed.');
    return;
  }

  const node = textNodesToTranslate[currentNodeIndex];
  const originalText = node.nodeValue;

  if (originalText) {
    activeTranslatingNode = node;
    originalTexts.set(node, originalText); // Save original text
    node.nodeValue = '[...translating]';   // Set placeholder
    chrome.runtime.sendMessage({ type: 'translate', text: originalText });
  } else {
    // If node has no text, skip it and move to the next one
    currentNodeIndex++;
    translateNextNode();
  }
}

/**
 * Handles incoming messages from the background script.
 */
chrome.runtime.onMessage.addListener((request: { type: string, delta?: string, error?: string }) => {
  if (!activeTranslatingNode) return;

  switch (request.type) {
    case 'translationStream':
      // On the first chunk, clear the placeholder text
      if (activeTranslatingNode.nodeValue === '[...translating]') {
        activeTranslatingNode.nodeValue = '';
      }
      // Append the translated chunk
      activeTranslatingNode.nodeValue += request.delta ?? '';
      break;

    case 'translationComplete':
      // Current node is done, move to the next one
      activeTranslatingNode = null;
      currentNodeIndex++;
      translateNextNode();
      break;

    case 'translationError':
      console.error('Translation Error:', request.error);
      // Restore the original text if an error occurs
      const originalText = originalTexts.get(activeTranslatingNode);
      if (originalText) {
        activeTranslatingNode.nodeValue = originalText;
      }
      // Move to the next node
      activeTranslatingNode = null;
      currentNodeIndex++;
      translateNextNode();
      break;
  }
});

/**
 * Initializes the translation process once the page is fully loaded.
 */
window.addEventListener('load', () => {
  // A small delay to ensure that dynamically loaded content is also included.
  setTimeout(() => {
    textNodesToTranslate = collectTextNodes(document.body);
    console.log(`Found ${textNodesToTranslate.length} text nodes to translate.`);
    translateNextNode();
  }, 1000);
});

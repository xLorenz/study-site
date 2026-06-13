// ── Study UI Extensions (Phase 2+) ──
// Loaded after chat-ui.js with defer. Contains selectNodeBySlug and future extensions.

(function() {
  'use strict';

  /**
   * selectNodeBySlug — Find a graph node by slug/id and select it.
   * Used by chat wikilinks to navigate to a concept in the graph + file tree.
   *
   * Flow: find node → set selectedNode → highlightFileInTree (opens preview)
   * Falls back to partial match on title/id if exact slug not found.
   */
  window.selectNodeBySlug = function(slug) {
    if (typeof graphNodes === 'undefined' || !graphNodes || graphNodes.length === 0) {
      if (typeof showToast === 'function') showToast('🔍 No graph loaded yet', 'info');
      return;
    }

    // 1. Exact match on node.id (which is the slug)
    const slugLower = slug.toLowerCase();
    let node = graphNodes.find(n => n.id.toLowerCase() === slugLower);

    // 2. Partial match on title or id
    if (!node) {
      node = graphNodes.find(n =>
        (n.title || '').toLowerCase().includes(slugLower) ||
        n.id.toLowerCase().includes(slugLower)
      );
    }

    if (!node) {
      if (typeof showToast === 'function') showToast('🔍 No wiki page found for "' + slug + '"', 'info');
      return;
    }

    // Select the node globally
    if (typeof selectedNode !== 'undefined') {
      selectedNode = node;
    }

    // Highlight in file tree (also opens file preview)
    if (typeof highlightFileInTree === 'function') {
      highlightFileInTree(node);
    }

    // Wake the graph loop so the selection is visible
    if (typeof resumeGraphLoop === 'function') {
      resumeGraphLoop();
    }
  };

  console.log('Study UI — Phase 2: selectNodeBySlug loaded');

  /**
   * highlightNodeFromFile — When a file tree item is clicked, highlight
   * the corresponding node in the graph. Bidirectional counterpart to
   * highlightFileInTree (which goes graph→tree).
   */
  window.highlightNodeFromFile = function(path) {
    if (typeof graphNodes === 'undefined' || !graphNodes) return;
    const fileName = path.split('/').pop().replace(/\.md$/i, '').toLowerCase();
    const node = graphNodes.find(n =>
      (n.label || '').toLowerCase() === fileName ||
      (n.title || '').toLowerCase() === fileName ||
      n.id.toLowerCase() === fileName
    );
    if (!node) return;
    if (typeof selectedNode !== 'undefined') selectedNode = node;
    if (typeof highlightFileInTree === 'function') highlightFileInTree(node);
    if (typeof resumeGraphLoop === 'function') resumeGraphLoop();
  };

  console.log('Study UI — Phase 5: highlightNodeFromFile loaded');

  // ── Phase 7: highlight_node tool state ──

  /**
   * Set of node IDs currently highlighted by the highlight_node chat tool.
   * Separate from selectedNode — both can be active simultaneously.
   */
  window._highlightedNodeIds = new Set();

  /**
   * highlightNodes — Called by chat-ui.js when a highlight_node tool result arrives.
   * Finds graph nodes matching the given slugs/names and adds them to the highlighted set.
   * Clears any previous highlights first.
   */
  window.highlightNodes = function(nodeNames) {
    window._highlightedNodeIds.clear();
    if (!nodeNames || nodeNames.length === 0) {
      if (typeof resumeGraphLoop === 'function') resumeGraphLoop();
      return;
    }
    if (typeof graphNodes === 'undefined' || !graphNodes) {
      if (typeof showToast === 'function') showToast('🔦 No graph loaded to highlight', 'info');
      return;
    }
    for (var i = 0; i < nodeNames.length; i++) {
      var slug = nodeNames[i].toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9\-]/g, '');
      // Exact match on node.id
      var node = graphNodes.find(function(n) { return n.id.toLowerCase() === slug; });
      // Fallback: partial match on title or id
      if (!node) {
        node = graphNodes.find(function(n) {
          return (n.title || '').toLowerCase().includes(slug) ||
                 n.id.toLowerCase().includes(slug);
        });
      }
      if (node) {
        window._highlightedNodeIds.add(node.id);
      }
    }
    if (window._highlightedNodeIds.size > 0) {
      if (typeof showToast === 'function') showToast('🔦 Highlighted ' + window._highlightedNodeIds.size + ' node(s) in graph', 'info');
    }
    if (typeof resumeGraphLoop === 'function') resumeGraphLoop();
  };

  /**
   * clearHighlightedNodes — Clear all highlighted node IDs.
   * Called when the user clicks empty space on the graph.
   */
  window.clearHighlightedNodes = function() {
    window._highlightedNodeIds.clear();
    if (typeof resumeGraphLoop === 'function') resumeGraphLoop();
  };

  console.log('Study UI — Phase 7: highlightNodes loaded');
})();

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
})();

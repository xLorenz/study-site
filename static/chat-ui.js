// ── Study Chat v4 - Polished Redesign ──
// Dual-path: background task guarantees completion, SSE provides real-time UI

(function() {
    'use strict';

    const chat = {
    messages: [],
    model: 'z-ai/glm-5.1',
    availableModels: [],
    streaming: false,
    currentSubject: null,
    abortController: null,
    currentAssistantMsg: null,
    currentBodyDiv: null,
    currentReasoningDiv: null,
    currentToolBoxes: [],
    currentReadGroup: null,
    currentToolCalls: [],
    currentFullContent: '',
    currentFullReasoning: '',
    };

    // ===========================
    // Render helper: marked → LaTeX → DOM
    // ===========================

    function renderContent(text, container) {
            // Pre-process: protect LaTeX from marked.js
            var placeholders = [];
            var counter = 0;
            function protect(regex, display) {
                text = text.replace(regex, function(match, inner) {
                    var id = 'LATEX_PH_' + counter + '_PH_';
                    counter++;
                    placeholders.push({id: id, inner: inner, display: display});
                    return id;
                });
            }
            // Display math: \[ ... \]  (model outputs literal backslash-bracket)
            protect(/\\\[([\s\S]*?)\\\]/g, true);
            // Inline math: \( ... \)
            protect(/\\\(([\s\S]*?)\\\)/g, false);
            // Display math: $$...$$
            protect(/\$\$([\s\S]*?)\$\$/g, true);
            // Inline math: $...$
            protect(/\$([^\n$]*?)\$/g, false);

            container.innerHTML = marked.parse(text, { gfm: true, breaks: true });

            // Restore LaTeX placeholders — render with KaTeX directly
            if (window.katex && placeholders.length > 0) {
                for (var i = 0; i < placeholders.length; i++) {
                    var p = placeholders[i];
                    try {
                        var html = katex.renderToString(p.inner, {
                            displayMode: p.display,
                            throwOnError: false
                        });
                        // Replace ALL occurrences of this placeholder
                        while (container.innerHTML.indexOf(p.id) !== -1) {
                            container.innerHTML = container.innerHTML.replace(p.id, html);
                        }
                    } catch(e) {
                        while (container.innerHTML.indexOf(p.id) !== -1) {
                            container.innerHTML = container.innerHTML.replace(p.id,
                                '<span class="math-error">' + p.inner + '</span>');
                        }
                    }
                }
            }
        }

    // ===========================
    // Init
    // ===========================

    window.initChat = function() {
        fetch('/api/model')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                chat.availableModels = data.available_models || ['z-ai/glm-5.1', 'deepseek-ai/deepseek-v4-flash'];
                chat.model = data.model || chat.availableModels[0];
                populateModelSelect();
            })
            ['catch'](function() {
                chat.availableModels = ['z-ai/glm-5.1', 'deepseek-ai/deepseek-v4-flash'];
                populateModelSelect();
            });

        document.getElementById('chat-send-btn').addEventListener('click', sendChatMessage);
        document.getElementById('chat-stop-btn').addEventListener('click', stopChat);
        document.getElementById('chat-clear-btn').addEventListener('click', clearChat);
        document.getElementById('chat-input').addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage(); }
        });
        document.getElementById('chat-input').addEventListener('input', autoResizeTextarea);
        initChatResize();
    };

    // ===========================
    // Send — Dual Path
    // ===========================

    function sendChatMessage() {
        if (chat.streaming || !chat.currentSubject) return;

        var input = document.getElementById('chat-input');
        var text = input.value.trim();
        if (!text) return;

        input.value = '';
        input.style.height = 'auto';
        setChatEnabled(false);

        // Add user message to UI
        addUserMessage(text);
        chat.messages.push({ role: 'user', content: text });

        // Keep last 19 messages for context
        var history = chat.messages.slice(-19);

        // Step 1: Start background task
        fetch('/api/chat-start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                subject: chat.currentSubject,
                message: text,
                conversation: history,
                model: chat.model
            })
        })
        .then(function(r) {
            if (!r.ok) throw new Error('Failed to start chat (' + r.status + ')');
            return r.json();
        })
        .then(function(data) {
            var taskId = data.task_id;

            // Step 2: Connect SSE stream
            chat.streaming = true;
            chat.abortController = new AbortController();
            showStopButton(true);
            createAssistantContainer();

            return fetch('/api/chat-stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task_id: taskId }),
                signal: chat.abortController.signal
            });
        })
        .then(function(streamRes) {
            if (!streamRes.ok) throw new Error('Stream error (' + streamRes.status + ')');

            var reader = streamRes.body.getReader();
            var decoder = new TextDecoder();
            var buffer = '';

            function readChunk() {
                return reader.read().then(function(result) {
                    if (result.done) return;

                    buffer += decoder.decode(result.value, { stream: true });
                    var lines = buffer.split('\n');
                    buffer = lines.pop() || '';

                    for (var i = 0; i < lines.length; i++) {
                        var trimmed = lines[i].trim();
                        if (trimmed.indexOf('data: ') !== 0) continue;
                        try {
                            handleEvent(JSON.parse(trimmed.slice(6)));
                        } catch(e) {
                            console.warn('SSE parse:', e.message);
                        }
                    }

                    return readChunk();
                });
            }

            return readChunk();
        })
        ['catch'](function(err) {
            if (err.name !== 'AbortError') {
                showChatError('Connection error: ' + err.message);
            }
        })
        ['finally'](function() {
            // Don't re-enable here — wait for done event
        });
    }

    function stopChat() {
    if (chat.abortController) {
    chat.abortController.abort();
    chat.streaming = false;
    showStopButton(false);
    if (chat.currentAssistantMsg) {
    chat.currentAssistantMsg.classList.remove('streaming');
    }
    if (chat.currentReasoningDiv) {
    chat.currentReasoningDiv.classList.remove('active');
    }
    if (chat.currentFullContent) {
    var msg = { role: 'assistant', content: chat.currentFullContent };
    if (chat.currentToolCalls.length > 0) msg.tool_calls = chat.currentToolCalls;
    chat.messages.push(msg);
    }
    setChatEnabled(true);
    chat.currentFullContent = '';
    chat.currentFullReasoning = '';
    chat.currentToolBoxes = [];
    chat.currentReadGroup = null;
    chat.currentToolCalls = [];
    chat.currentAssistantMsg = null;
    chat.currentBodyDiv = null;
    chat.currentReasoningDiv = null;
    }
    }

            function handleEvent(event) {
        switch (event.type) {
            case 'token':
                chat.currentFullContent += event.content;
                if (chat.currentBodyDiv) {
                    renderContent(chat.currentFullContent, chat.currentBodyDiv);
                }
                smartScroll();
                break;

            case 'reasoning':
                chat.currentFullReasoning += event.content;
                if (chat.currentReasoningDiv) {
                    var body = chat.currentReasoningDiv.querySelector('.reasoning-body');
                    var count = chat.currentReasoningDiv.querySelector('.reasoning-char-count');
                    if (body) {
                        body.textContent = chat.currentFullReasoning;
                    }
                    if (count) {
                        count.textContent = chat.currentFullReasoning.length + ' chars';
                    }
                    chat.currentReasoningDiv.classList.add('active');
                    if (chat.currentAssistantMsg) {
                        chat.currentAssistantMsg.classList.add('has-reasoning');
                    }
                }
                smartScroll();
                break;

            case 'tool_call': {
            var args = safeParse(event.arguments, {});
            var isRead = event.name === 'read_vault_file';
            var label = isRead ? (args.path || 'file') : (args.filename || 'object');
            // Track for persistence
            chat.currentToolCalls.push({ name: event.name, arguments: event.arguments, label: label });
            if (isRead) {
            if (chat.currentReadGroup) {
            addToReadGroup(chat.currentReadGroup, label);
            } else {
            var group = createReadGroup();
            chat.currentReadGroup = group;
            if (chat.currentBodyDiv) {
            chat.currentBodyDiv.parentNode.insertBefore(group, chat.currentBodyDiv.nextSibling);
            }
            addToReadGroup(group, label);
            }
            } else {
            var box = createToolBox(isRead, label, event.name);
            chat.currentToolBoxes.push(box);
            if (chat.currentBodyDiv) {
            var insertBefore = chat.currentReadGroup ? chat.currentReadGroup.nextSibling : chat.currentBodyDiv.nextSibling;
            chat.currentBodyDiv.parentNode.insertBefore(box, insertBefore);
            }
            }
            smartScroll();
            break;
            }

            case 'tool_result':
            if (event.name === 'read_vault_file' && chat.currentReadGroup) {
            completeReadGroupItem(chat.currentReadGroup, event);
            } else {
            for (var i = 0; i < chat.currentToolBoxes.length; i++) {
            var box = chat.currentToolBoxes[i];
            if (box.dataset.toolName === event.name && !box.classList.contains('completed')) {
            completeToolBox(box);
            break;
            }
            }
            // Auto-refresh objects tab when a study object or video is created
            if ((event.name === 'write_study_object' || event.name === 'write_study_video') && chat.currentSubject && typeof window.reloadObjectTree === 'function') {
            window.reloadObjectTree(chat.currentSubject);
            }
            }
            smartScroll();
            break;

            case 'done':
            if (event.content) {
            chat.currentFullContent = event.content;
            if (chat.currentBodyDiv) {
            renderContent(chat.currentFullContent, chat.currentBodyDiv);
            }
            }
            if (chat.currentReasoningDiv) {
            chat.currentReasoningDiv.classList.remove('active');
            }
            if (chat.currentAssistantMsg) {
            chat.currentAssistantMsg.classList.remove('streaming');
            }
            highlightWikilinks(chat.currentBodyDiv);
            var doneMsg = { role: 'assistant', content: chat.currentFullContent };
            if (chat.currentToolCalls.length > 0) doneMsg.tool_calls = chat.currentToolCalls;
            chat.messages.push(doneMsg);
            setChatEnabled(true);
            chat.streaming = false;
            showStopButton(false);
            chat.currentFullContent = '';
            chat.currentFullReasoning = '';
            chat.currentToolBoxes = [];
            chat.currentReadGroup = null;
            chat.currentToolCalls = [];
            chat.currentAssistantMsg = null;
            chat.currentBodyDiv = null;
            chat.currentReasoningDiv = null;
            smartScroll();
            break;

                case 'error':
                showChatError(event.message || 'Error');
                setChatEnabled(true);
                chat.streaming = false;
                showStopButton(false);
                chat.currentFullContent = '';
                chat.currentFullReasoning = '';
                chat.currentToolBoxes = [];
                chat.currentReadGroup = null;
                chat.currentAssistantMsg = null;
                chat.currentBodyDiv = null;
                chat.currentReasoningDiv = null;
                break;
                }
                }

    // ===========================
    // DOM Helpers
    // ===========================

    function createAssistantContainer() {
        chat.currentFullContent = '';
        chat.currentFullReasoning = '';
        chat.currentToolBoxes = [];
        chat.currentReadGroup = null;
        chat.currentToolCalls = [];

        var msgDiv = document.createElement('div');
        msgDiv.className = 'chat-msg assistant streaming';
        msgDiv.id = 'streaming-msg';

        // Remove placeholder if present
        var placeholder = document.getElementById('chat-placeholder');
        if (placeholder) placeholder.style.display = 'none';

        // Reasoning box
        var reasonDiv = document.createElement('div');
        reasonDiv.className = 'msg-reasoning';

        var reasonHeader = document.createElement('div');
        reasonHeader.className = 'reasoning-header';
        reasonHeader.innerHTML = '<span class="reasoning-label">\uD83E\uDDE0 Reasoning</span>';
        var toggleBtn = document.createElement('button');
        toggleBtn.className = 'reasoning-toggle';
        toggleBtn.textContent = 'Collapse';
        reasonHeader.appendChild(toggleBtn);
        reasonDiv.appendChild(reasonHeader);

        var reasonBody = document.createElement('div');
        reasonBody.className = 'reasoning-body collapsed';
        reasonDiv.appendChild(reasonBody);

        var charCount = document.createElement('span');
        charCount.className = 'reasoning-char-count';
        reasonBody.appendChild(charCount);

        var collapsed = true;
        reasonHeader.addEventListener('click', function() {
            collapsed = !collapsed;
            reasonBody.classList.toggle('collapsed', collapsed);
            toggleBtn.textContent = collapsed ? 'Expand' : 'Collapse';
        });

        msgDiv.appendChild(reasonDiv);
        chat.currentReasoningDiv = reasonDiv;

        // Body div
        var bodyDiv = document.createElement('div');
        bodyDiv.className = 'chat-body';
        msgDiv.appendChild(bodyDiv);
        chat.currentBodyDiv = bodyDiv;

        var container = document.getElementById('chat-messages');
        container.appendChild(msgDiv);
        chat.currentAssistantMsg = msgDiv;
        smartScroll();
    }

    function createToolBox(isRead, label, toolName) {
        var box = document.createElement('div');
        box.className = 'msg-tool-box';
        box.dataset.toolName = toolName || (isRead ? 'read_vault_file' : 'write_study_object');

        var icon = document.createElement('span');
        icon.className = 'tool-icon';
        icon.textContent = isRead ? '\uD83D\uDCD6' : '\u270F\uFE0F';
        box.appendChild(icon);

        var labelSpan = document.createElement('span');
        labelSpan.className = 'tool-label';
        labelSpan.innerHTML = (isRead ? 'reading ' : 'creating ') + '<code>' + escapeHtml(label) + '</code>';
        box.appendChild(labelSpan);

        var dots = document.createElement('span');
        dots.className = 'dots';
        dots.innerHTML = '<span></span><span></span><span></span>';
        box.appendChild(dots);

        return box;
    }

    function completeToolBox(box) {
    box.classList.add('completed');
    var icon = box.querySelector('.tool-icon');
    var label = box.querySelector('.tool-label code');
    var labelText = label ? label.textContent : '';
    var isRead = box.dataset.toolName === 'read_vault_file';
    if (icon) icon.textContent = isRead ? '\uD83D\uDCD6' : '\u2705';
    var labelSpan = box.querySelector('.tool-label');
    if (labelSpan) {
    labelSpan.innerHTML = (isRead ? 'read ' : 'created ') + '<code>' + escapeHtml(labelText) + '</code>';
    }
    }

    // ── Read Group (collapsible dropdown for multiple reads) ──

    function createReadGroup() {
    var group = document.createElement('div');
    group.className = 'msg-tool-read-group';

    var header = document.createElement('div');
    header.className = 'read-group-header';
    header.innerHTML = '<span class="read-group-icon">\uD83D\uDCD6</span><span class="read-group-label">read <strong>0</strong> files</span><span class="read-group-toggle">\u25B8</span>';
    group.appendChild(header);

    var list = document.createElement('div');
    list.className = 'read-group-list collapsed';
    group.appendChild(list);

    header.addEventListener('click', function() {
    var isCollapsed = list.classList.contains('collapsed');
    list.classList.toggle('collapsed', !isCollapsed);
    header.querySelector('.read-group-toggle').textContent = isCollapsed ? '\u25BE' : '\u25B8';
    });

    group._count = 0;
    return group;
    }

    function addToReadGroup(group, label) {
    var item = document.createElement('div');
    item.className = 'read-group-item';
    item.dataset.label = label;
    item.innerHTML = '<span class="read-group-item-icon">\uD83D\uDCD6</span><code>' + escapeHtml(label) + '</code><span class="dots"><span></span><span></span><span></span></span>';
    group.querySelector('.read-group-list').appendChild(item);
    group._count++;
    var countSpan = group.querySelector('.read-group-label strong');
    if (countSpan) countSpan.textContent = group._count;
    }

    function completeReadGroupItem(group, event) {
    var list = group.querySelector('.read-group-list');
    if (!list) return;
    var items = list.querySelectorAll('.read-group-item');
    for (var i = items.length - 1; i >= 0; i--) {
    if (!items[i].classList.contains('completed')) {
    items[i].classList.add('completed');
    var dots = items[i].querySelector('.dots');
    if (dots) dots.remove();
    var icon = items[i].querySelector('.read-group-item-icon');
    if (icon) icon.textContent = '\u2705';
    break;
    }
    }
    }

    // ── Render tool calls from saved history ──

    function renderToolCalls(div, toolCalls) {
    if (!toolCalls || toolCalls.length === 0) return;

    var reads = [];
    var writes = [];
    for (var i = 0; i < toolCalls.length; i++) {
    var tc = toolCalls[i];
    if (tc.name === 'read_vault_file') {
    reads.push(tc.label || 'file');
    } else {
    writes.push(tc);
    }
    }

    // Render read group
    if (reads.length > 0) {
    var group = createReadGroup();
    for (var j = 0; j < reads.length; j++) {
    addToReadGroup(group, reads[j]);
    completeReadGroupItem(group);
    }
    div.insertBefore(group, div.firstChild);
    }

    // Render write tool boxes
    for (var k = 0; k < writes.length; k++) {
    var w = writes[k];
    var box = document.createElement('div');
    box.className = 'msg-tool-box completed';
    box.dataset.toolName = w.name || 'write_study_object';
    box.innerHTML = '<span class="tool-icon">\u2705</span><span class="tool-label">created <code>' + escapeHtml(w.label || 'object') + '</code></span>';
    div.insertBefore(box, div.firstChild);
    }
    }

    function addUserMessage(text) {
        var div = document.createElement('div');
        div.className = 'chat-msg user';
        div.textContent = text;
        var container = document.getElementById('chat-messages');
        var placeholder = document.getElementById('chat-placeholder');
        if (placeholder) placeholder.style.display = 'none';
        container.appendChild(div);
        smartScroll();
    }

    function showChatError(msg) {
        var placeholder = document.getElementById('streaming-msg');
        if (placeholder) placeholder.remove();

        var div = document.createElement('div');
        div.className = 'chat-error';
        div.textContent = msg;
        document.getElementById('chat-messages').appendChild(div);
        smartScroll();
    }

    function highlightWikilinks(container) {
        if (!container) return;
        var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
        var nodesToReplace = [];
        while (walker.nextNode()) {
            var node = walker.currentNode;
            var text = node.textContent;
            var regex = /\[\[([^\]]+)\]\]/g;
            var match;
            var lastIdx = 0;
            var fragment = document.createDocumentFragment();

            while ((match = regex.exec(text)) !== null) {
                if (match.index > lastIdx) {
                    fragment.appendChild(document.createTextNode(text.slice(lastIdx, match.index)));
                }
                var link = document.createElement('span');
                link.className = 'wikilink';
                link.textContent = match[1];
                link.title = 'Open wiki: ' + match[1];
                link.addEventListener('click', (function(name) {
                    return function() {
                        openWikilink(name);
                    };
                })(match[1]));
                fragment.appendChild(link);
                lastIdx = match.index + match[0].length;
            }

            if (lastIdx > 0) {
                if (lastIdx < text.length) {
                    fragment.appendChild(document.createTextNode(text.slice(lastIdx)));
                }
                nodesToReplace.push({ old: node, new: fragment });
            }
        }

        for (var i = 0; i < nodesToReplace.length; i++) {
            nodesToReplace[i].old.parentNode.replaceChild(nodesToReplace[i].new, nodesToReplace[i].old);
        }
    }

    function openWikilink(name) {
        var slug = name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9\-]/g, '');
        if (window.selectNodeBySlug) {
            window.selectNodeBySlug(slug);
        }
        showToast('Searching: ' + name, 'info');
    }

    function setChatEnabled(enabled) {
        var btn = document.getElementById('chat-send-btn');
        var input = document.getElementById('chat-input');
        if (btn) btn.disabled = !enabled;
        if (input) input.disabled = !enabled;
        if (enabled) {
            input.focus();
        }
    }

    function showStopButton(visible) {
        var btn = document.getElementById('chat-stop-btn');
        if (!btn) return;
        btn.classList.toggle('active', visible);
    }

    function smartScroll() {
        var container = document.getElementById('chat-messages');
        if (!container) return;
        var threshold = 60;
        var isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < threshold;
        if (isNearBottom) {
            container.scrollTop = container.scrollHeight;
        }
    }

    function autoResizeTextarea() {
        var el = this;
        el.style.height = 'auto';
        el.style.height = Math.min(el.scrollHeight, 160) + 'px';
    }

    function escapeHtml(text) {
        if (typeof text !== 'string') return '';
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(text));
        return div.innerHTML;
    }

    function safeParse(json, fallback) {
        try {
            return JSON.parse(json);
        } catch(e) {
            return fallback;
        }
    }

    // ===========================
    // Clear Chat
    // ===========================

    function clearChat() {
        if (chat.streaming) return;
        if (!chat.currentSubject) return;
        if (chat.messages.length === 0) return;

        chat.messages = [];
        chat.currentFullContent = '';
        chat.currentFullReasoning = '';
        chat.currentToolBoxes = [];
        chat.currentAssistantMsg = null;
        chat.currentBodyDiv = null;
        chat.currentReasoningDiv = null;

        var container = document.getElementById('chat-messages');
        if (container) {
            container.innerHTML = '';
            var ph = document.createElement('div');
            ph.className = 'chat-placeholder';
            ph.id = 'chat-placeholder';
            ph.innerHTML = '<div class="icon">\uD83D\uDCDD</div><div class="main-text">Ask a question about <strong>' + escapeHtml(chat.currentSubject) + '</strong></div><div class="sub-text">Chat has been cleared</div>';
            container.appendChild(ph);
        }

        fetch('/api/chat-save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                subject: chat.currentSubject,
                messages: []
            })
        })['catch'](function() {});

        showToast('Chat cleared', 'info');
    }

    // ===========================
    // Persistence
    // ===========================

    window.loadChat = function() {
        if (!chat.currentSubject) return;
        var container = document.getElementById('chat-messages');
        if (container) container.innerHTML = '';

        // Update subject badge
        var badge = document.getElementById('chat-subject-badge');
        if (badge) {
            badge.textContent = chat.currentSubject;
            badge.classList.add('active');
        }

        fetch('/api/chat-load?subject=' + encodeURIComponent(chat.currentSubject))
            .then(function(r) { return r.json(); })
            .then(function(data) {
                chat.messages = data.messages || [];
                renderHistory();
            })
            ['catch'](function() {
                chat.messages = [];
                renderHistory();
            });

        setChatEnabled(!chat.streaming);
    };

    window.setChatSubject = function(subject) {
        // Save current chat before switching
        window.saveCurrentChat();

        chat.currentSubject = subject || null;
        chat.messages = [];
        chat.currentFullContent = '';
        chat.currentFullReasoning = '';
        chat.currentToolBoxes = [];

        // Reset UI
        var container = document.getElementById('chat-messages');
        if (container) {
            container.innerHTML = '';
        }

        // Update subject badge
        var badge = document.getElementById('chat-subject-badge');
        if (badge) {
            if (subject) {
                badge.textContent = subject;
                badge.classList.add('active');
            } else {
                badge.classList.remove('active');
            }
        }

        if (subject) {
            // Show loading state with subject name
            var loading = document.createElement('div');
            loading.className = 'chat-placeholder';
            loading.id = 'chat-placeholder';
            loading.innerHTML = '<div class="icon">\uD83D\uDCDA</div><div class="main-text"><strong>' + escapeHtml(subject) + '</strong></div><div class="sub-text">Loading conversation...</div>';
            if (container) container.appendChild(loading);
            window.loadChat();
        } else {
            if (container) {
                var ph = document.createElement('div');
                ph.className = 'chat-placeholder';
                ph.id = 'chat-placeholder';
                ph.innerHTML = '<div class="icon">\uD83D\uDCAC</div><div class="main-text">Select a subject to start chatting</div><div class="sub-text">Click a node on the graph or pick one from the header</div>';
                container.appendChild(ph);
            }
            setChatEnabled(false);
        }
    };

    function renderHistory() {
        var container = document.getElementById('chat-messages');
        if (!container) return;

        var placeholder = document.getElementById('chat-placeholder');
        if (placeholder) placeholder.style.display = 'none';
        container.innerHTML = '';

        if (!chat.messages || chat.messages.length === 0) {
            var ph = document.createElement('div');
            ph.className = 'chat-placeholder';
            ph.id = 'chat-placeholder';
            ph.innerHTML = '<div class="icon">\uD83D\uDCDD</div><div class="main-text">Ask a question about <strong>' + escapeHtml(chat.currentSubject || 'this subject') + '</strong></div><div class="sub-text">Start a conversation to learn</div>';
            container.appendChild(ph);
            return;
        }

        for (var i = 0; i < chat.messages.length; i++) {
        var msg = chat.messages[i];
        if (msg.role === 'user') {
        var div = document.createElement('div');
        div.className = 'chat-msg user';
        div.textContent = msg.content;
        container.appendChild(div);
        } else if (msg.role === 'assistant') {
        var div = document.createElement('div');
        div.className = 'chat-msg assistant';
        // Render tool calls before body
        if (msg.tool_calls && msg.tool_calls.length > 0) {
        renderToolCalls(div, msg.tool_calls);
        }
        var body = document.createElement('div');
        body.className = 'chat-body';
        renderContent(msg.content || '', body);
        div.appendChild(body);
        container.appendChild(div);
        highlightWikilinks(body);
        }
        }
         // Force scroll to bottom on load
         setTimeout(function() {
         container.scrollTop = container.scrollHeight;
         }, 100);
    }

    window.saveCurrentChat = function() {
        if (chat.currentSubject && chat.messages.length > 0) {
            fetch('/api/chat-save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    subject: chat.currentSubject,
                    messages: chat.messages
                })
            })['catch'](function() {});
        }
    };

    // ===========================
    // Model Selector
    // ===========================

    function populateModelSelect() {
        var select = document.getElementById('chat-model-select');
        if (!select) return;
        select.innerHTML = '';

        for (var i = 0; i < chat.availableModels.length; i++) {
            var model = chat.availableModels[i];
            var opt = document.createElement('option');
            opt.value = model;
            var parts = model.split('/');
            opt.textContent = parts[parts.length - 1] || model;
            if (model === chat.model) opt.selected = true;
            select.appendChild(opt);
        }

        select.addEventListener('change', function() {
            chat.model = select.value;
        });
    }

    // ===========================
    // Resize Handle — 75/25 split
    // ===========================

    function initChatResize() {
     // Handled by initChatResize() in index.html
     // (needs sidebar-left reference which is cleaner from the HTML context)
    }

})();

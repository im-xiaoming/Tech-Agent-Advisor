// Tech ChatBot - Main JavaScript

// DOM Elements
const sidebar = document.getElementById('sidebar');
const toggleSidebar = document.getElementById('toggleSidebar');
const desktopOpenSidebar = document.getElementById('desktopOpenSidebar');
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
const newChatBtn = document.getElementById('newChatBtn');
const mobileNewChat = document.getElementById('mobileNewChat');
const settingsBtn = document.getElementById('settingsBtn');
const settingsModal = document.getElementById('settingsModal');
const closeSettings = document.getElementById('closeSettings');
const deleteModal = document.getElementById('deleteModal');
const closeDeleteModal = document.getElementById('closeDeleteModal');
const cancelDelete = document.getElementById('cancelDelete');
const confirmDelete = document.getElementById('confirmDelete');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const chatContainer = document.getElementById('chatContainer');
const welcomeScreen = document.getElementById('welcomeScreen');
const messagesArea = document.getElementById('messagesArea');
const darkModeToggle = document.getElementById('darkModeToggle');
const fontSizeSelect = document.getElementById('fontSizeSelect');
const saveHistoryToggle = document.getElementById('saveHistoryToggle');
const enterSendToggle = document.getElementById('enterSendToggle');
const xianxiaToggle = document.getElementById('xianxiaToggle');
const clearHistoryBtn = document.getElementById('clearHistoryBtn');
const exportDataBtn = document.getElementById('exportDataBtn');
const todayHistory = document.getElementById('todayHistory');
const weekHistory = document.getElementById('weekHistory');
const monthHistory = document.getElementById('monthHistory');
const mainContent = document.getElementById('mainContent');
const chatApiUrl = mainContent?.dataset.chatApiUrl || '/message/';
const chatHistoryUrl = mainContent?.dataset.chatHistoryUrl || '';
const chatHistoryClearUrl = mainContent?.dataset.chatHistoryClearUrl || '';
const activeChatStorageKey = 'techChatActiveId';
const newChatSentinel = '__new_chat__';

// State
let currentChatId = null;
let chats = [];
let isAwaitingResponse = false;
let settings = {
    darkMode: false,
    fontSize: 'medium',
    saveHistory: true,
    enterSend: true,
    xianxiaEffect: true
};
let deleteTargetId = null;

// Initialize
async function init() {
    loadSettings();
    applySettings();
    setupEventListeners();
    await loadChats();
    renderChatHistory();
    restoreActiveChat();
}

// Load settings from localStorage
function loadSettings() {
    const savedSettings = localStorage.getItem('techChatSettings');
    if (savedSettings) {
        settings = { ...settings, ...JSON.parse(savedSettings) };
    }
}

// Save settings to localStorage
function saveSettings() {
    localStorage.setItem('techChatSettings', JSON.stringify(settings));
}

// Apply settings to UI
function applySettings() {
    // Dark mode
    if (settings.darkMode) {
        document.documentElement.setAttribute('data-theme', 'dark');
        darkModeToggle.checked = true;
    } else {
        document.documentElement.removeAttribute('data-theme');
        darkModeToggle.checked = false;
    }
    
    // Font size
    document.documentElement.setAttribute('data-font-size', settings.fontSize);
    fontSizeSelect.value = settings.fontSize;
    
    // Other toggles
    saveHistoryToggle.checked = settings.saveHistory;
    enterSendToggle.checked = settings.enterSend;
    xianxiaToggle.checked = settings.xianxiaEffect;
}

function getCsrfToken() {
    const tokenInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (tokenInput?.value) return tokenInput.value;

    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
}

function getLocalChats() {
    const savedChats = localStorage.getItem('techChatHistory');
    if (savedChats) {
        return JSON.parse(savedChats);
    }
    return [];
}

function getChatActivityTime(chat) {
    const messages = Array.isArray(chat.messages) ? chat.messages : [];
    const lastMessage = messages[messages.length - 1];
    const candidates = [
        lastMessage?.timestamp,
        chat.updatedAt,
        chat.createdAt,
    ];

    for (const value of candidates) {
        const time = value ? new Date(value).getTime() : NaN;
        if (Number.isFinite(time)) return time;
    }
    return 0;
}

function sortChatsByActivity(items = chats) {
    return [...items].sort((a, b) => getChatActivityTime(b) - getChatActivityTime(a));
}

function normalizeChats(items) {
    return sortChatsByActivity(
        (Array.isArray(items) ? items : [])
            .filter(chat => chat && chat.id)
            .map(chat => ({
                ...chat,
                messages: Array.isArray(chat.messages) ? chat.messages : [],
                createdAt: chat.createdAt || chat.created_at || new Date().toISOString(),
                updatedAt: chat.updatedAt || chat.updated_at || chat.createdAt || chat.created_at || new Date().toISOString(),
            }))
    );
}

function persistActiveChatId(chatId) {
    if (chatId) {
        localStorage.setItem(activeChatStorageKey, chatId);
    } else {
        localStorage.setItem(activeChatStorageKey, newChatSentinel);
    }
}

function restoreActiveChat() {
    const savedChatId = localStorage.getItem(activeChatStorageKey);
    if (savedChatId === newChatSentinel) return;
    if (savedChatId && chats.some(chat => chat.id === savedChatId)) {
        loadChat(savedChatId);
        return;
    }

    const [mostRecentChat] = sortChatsByActivity();
    if (mostRecentChat) {
        loadChat(mostRecentChat.id);
    }
}

// Load chats from server, with localStorage as a fallback.
async function loadChats() {
    const localChats = getLocalChats();

    if (!chatHistoryUrl) {
        chats = normalizeChats(localChats);
        return;
    }

    try {
        const response = await fetch(chatHistoryUrl, {
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' },
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        chats = normalizeChats(data.chats);

        if (chats.length === 0 && localChats.length > 0) {
            chats = normalizeChats(localChats);
            await saveChats();
        }
    } catch (error) {
        chats = normalizeChats(localChats);
        showToast('Could not load server history. Using local history.', 'error');
    }
}

// Save chats to localStorage and server.
async function saveChats() {
    if (!settings.saveHistory) return;

    localStorage.setItem('techChatHistory', JSON.stringify(chats));

    if (!chatHistoryUrl) return;

    try {
        const response = await fetch(chatHistoryUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({ chats }),
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
    } catch (error) {
        showToast('Could not save history to server.', 'error');
    }
}

// Render chat history in sidebar
function renderChatHistory() {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
    const monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
    
    const todayChats = [];
    const weekChats = [];
    const monthChats = [];
    
    sortChatsByActivity().forEach(chat => {
        const chatDate = new Date(getChatActivityTime(chat));
        if (chatDate >= today) {
            todayChats.push(chat);
        } else if (chatDate >= weekAgo) {
            weekChats.push(chat);
        } else if (chatDate >= monthAgo) {
            monthChats.push(chat);
        }
    });
    
    todayHistory.innerHTML = todayChats.map(chat => createHistoryItemHTML(chat)).join('');
    weekHistory.innerHTML = weekChats.map(chat => createHistoryItemHTML(chat)).join('');
    monthHistory.innerHTML = monthChats.map(chat => createHistoryItemHTML(chat)).join('');
    
    // Add click listeners
    document.querySelectorAll('.history-item').forEach(item => {
        item.addEventListener('click', (e) => {
            if (!e.target.closest('.history-action-btn')) {
                loadChat(item.dataset.id);
            }
        });
    });
    
    document.querySelectorAll('.history-action-btn.delete').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            showDeleteConfirmation(btn.dataset.id);
        });
    });
}

// Create history item HTML
function createHistoryItemHTML(chat) {
    const isActive = chat.id === currentChatId ? 'active' : '';
    return `
        <div class="history-item ${isActive}" data-id="${chat.id}">
            <span class="history-item-title">${escapeHtml(chat.title)}</span>
            <div class="history-item-actions">
                <button class="history-action-btn delete" data-id="${chat.id}" title="Delete">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            </div>
        </div>
    `;
}

// Setup event listeners
function setupEventListeners() {
    // Sidebar toggle
    toggleSidebar.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
    });

    desktopOpenSidebar.addEventListener('click', () => {
        sidebar.classList.remove('collapsed');
    });
    
    // Mobile menu
    mobileMenuBtn.addEventListener('click', () => {
        sidebar.classList.add('mobile-open');
        showOverlay();
    });
    
    // New chat
    newChatBtn.addEventListener('click', startNewChat);
    mobileNewChat.addEventListener('click', startNewChat);
    
    // Settings
    settingsBtn.addEventListener('click', () => {
        settingsModal.classList.add('active');
    });
    
    closeSettings.addEventListener('click', () => {
        settingsModal.classList.remove('active');
    });
    
    settingsModal.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
            settingsModal.classList.remove('active');
        }
    });
    
    // Delete modal
    closeDeleteModal.addEventListener('click', hideDeleteModal);
    cancelDelete.addEventListener('click', hideDeleteModal);
    confirmDelete.addEventListener('click', () => {
        if (deleteTargetId) {
            deleteChat(deleteTargetId);
            hideDeleteModal();
        }
    });
    
    deleteModal.addEventListener('click', (e) => {
        if (e.target === deleteModal) {
            hideDeleteModal();
        }
    });
    
    // Settings changes
    darkModeToggle.addEventListener('change', () => {
        settings.darkMode = darkModeToggle.checked;
        applySettings();
        saveSettings();
    });
    
    fontSizeSelect.addEventListener('change', () => {
        settings.fontSize = fontSizeSelect.value;
        applySettings();
        saveSettings();
    });
    
    saveHistoryToggle.addEventListener('change', () => {
        settings.saveHistory = saveHistoryToggle.checked;
        saveSettings();
    });
    
    enterSendToggle.addEventListener('change', () => {
        settings.enterSend = enterSendToggle.checked;
        saveSettings();
    });

    xianxiaToggle.addEventListener('change', () => {
        settings.xianxiaEffect = xianxiaToggle.checked;
        saveSettings();
    });
    
    clearHistoryBtn.addEventListener('click', async () => {
        if (confirm('Are you sure you want to clear all chat history?')) {
            chats = [];
            localStorage.removeItem('techChatHistory');
            await clearServerHistory();
            renderChatHistory();
            startNewChat();
            showToast('All history cleared', 'success');
        }
    });
    
    exportDataBtn.addEventListener('click', exportData);
    
    // Message input
    messageInput.addEventListener('input', autoResize);
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey && settings.enterSend) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    sendBtn.addEventListener('click', sendMessage);
    
    // Suggestion cards
    document.querySelectorAll('.suggestion-card').forEach(card => {
        card.addEventListener('click', () => {
            const prompt = card.dataset.prompt;
            messageInput.value = prompt;
            sendMessage();
        });
    });
}

// Auto resize textarea
function autoResize() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
}

// Start new chat
function startNewChat() {
    currentChatId = null;
    persistActiveChatId(null);
    messagesArea.innerHTML = '';
    welcomeScreen.classList.remove('hidden');
    messagesArea.classList.remove('active');
    messageInput.value = '';
    autoResize();
    
    // Close mobile sidebar
    sidebar.classList.remove('mobile-open');
    hideOverlay();
    
    // Update active state in history
    document.querySelectorAll('.history-item').forEach(item => {
        item.classList.remove('active');
    });
}

// Load chat
function loadChat(chatId) {
    const chat = chats.find(c => c.id === chatId);
    if (!chat) return;
    
    currentChatId = chatId;
    persistActiveChatId(chatId);
    welcomeScreen.classList.add('hidden');
    messagesArea.classList.add('active');
    
    // Render messages
    messagesArea.innerHTML = chat.messages.map(msg => createMessageHTML(msg)).join('');
    
    // Scroll to bottom
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    // Close mobile sidebar
    sidebar.classList.remove('mobile-open');
    hideOverlay();
    
    // Update active state
    renderChatHistory();
}

// Create message HTML
function createMessageHTML(message) {
    const isUser = message.role === 'user';
    const avatarContent = isUser ? 'You' : 'AI';
    
    return `
        <div class="message ${message.role}">
            <div class="message-avatar">${avatarContent}</div>
            <div class="message-content">
                ${formatMessageContent(message.content)}
                <div class="message-actions">
                    <button class="message-action-btn" onclick="copyMessage(this)" title="Copy">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    `;
}

// Format message content (basic markdown)
function formatMessageContent(content) {
    return `<div class="message-markdown">${formatMessageBody(content)}</div>`;
}

function formatMessageBody(content) {
    // Escape HTML first
    let formatted = escapeHtml(content || '');
    formatted = formatted.replace(/&lt;br\s*\/?&gt;/gi, '<br>');
    
    // Code blocks
    formatted = formatted.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
    
    // Inline code
    formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Bold italic
    formatted = formatted.replace(/\*\*\*([\s\S]+?)\*\*\*/g, '<strong><em>$1</em></strong>');

    // Bold
    formatted = formatted.replace(/\*\*([\s\S]+?)\*\*/g, '<strong>$1</strong>');
    
    // Italic
    formatted = formatted.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
    
    return formatMarkdownBlocks(formatted);
}

function formatMarkdownBlocks(content) {
    const lines = normalizeMarkdownTables(content).split('\n');
    const output = [];
    let openList = null;
    let tableRows = [];

    const closeList = () => {
        if (!openList) return;
        output.push(`</${openList}>`);
        openList = null;
    };

    const flushTable = () => {
        if (!tableRows.length) return;

        closeList();
        if (tableRows.length < 2) {
            tableRows.forEach(row => output.push(`<p>${row}</p>`));
            tableRows = [];
            return;
        }

        const rows = tableRows.map(parseTableCells);
        const header = rows[0];
        const bodyRows = rows.slice(isTableSeparator(rows[1]) ? 2 : 1)
            .filter(row => !isTableSeparator(row));

        output.push('<div class="message-table-wrap"><table><thead><tr>');
        header.forEach(cell => output.push(`<th>${cell}</th>`));
        output.push('</tr></thead><tbody>');
        bodyRows.forEach(row => {
            output.push('<tr>');
            header.forEach((_, index) => output.push(`<td>${row[index] || ''}</td>`));
            output.push('</tr>');
        });
        output.push('</tbody></table></div>');
        tableRows = [];
    };

    lines.forEach(line => {
        const trimmed = line.trim();

        if (!trimmed) {
            flushTable();
            closeList();
            return;
        }

        if (isTableRow(trimmed)) {
            tableRows.push(trimmed);
            return;
        }

        flushTable();

        const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
        if (heading) {
            closeList();
            const level = Math.min(heading[1].length + 1, 4);
            output.push(`<h${level}>${heading[2]}</h${level}>`);
            return;
        }

        const bullet = trimmed.match(/^[-*]\s+(.+)$/);
        if (bullet) {
            if (openList !== 'ul') {
                closeList();
                output.push('<ul>');
                openList = 'ul';
            }
            output.push(`<li>${bullet[1]}</li>`);
            return;
        }

        const numbered = trimmed.match(/^\d+\.\s+(.+)$/);
        if (numbered) {
            if (openList !== 'ol') {
                closeList();
                output.push('<ol>');
                openList = 'ol';
            }
            output.push(`<li>${numbered[1]}</li>`);
            return;
        }

        closeList();
        output.push(`<p>${trimmed}</p>`);
    });

    flushTable();
    closeList();
    return output.join('');
}

function normalizeMarkdownTables(content) {
    return content.replace(/(\|[^\n]*\|)\n\s*\n(?=\s*\|)/g, '$1\n');
}

function isTableRow(line) {
    return isPipeTableRow(line) || isTabTableRow(line);
}

function parseTableCells(line) {
    if (isTabTableRow(line)) {
        return line.split('\t').map(cell => cell.trim());
    }

    return line
        .replace(/^\|/, '')
        .replace(/\|$/, '')
        .split('|')
        .map(cell => cell.trim());
}

function isPipeTableRow(line) {
    return line.startsWith('|') && line.endsWith('|') && line.split('|').length > 2;
}

function isTabTableRow(line) {
    return line.includes('\t') && line.split('\t').filter(cell => cell.trim()).length > 1;
}

function isTableSeparator(row) {
    return row.length > 0 && row.every(cell => /^:?-{3,}:?$/.test(cell.trim()));
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function buildRequestHistory(limit = 30) {
    const chat = chats.find(c => c.id === currentChatId);
    if (!chat || !Array.isArray(chat.messages)) return [];

    return chat.messages
        .slice(0, -1)
        .slice(-limit)
        .map(message => {
            const speaker = message.role === 'user' ? 'Người dùng' : 'Trợ lý';
            return `${message.role === 'user' ? 'User' : 'Assistant'}: ${message.content || ''}`;
        });
}

// Send message
function sendMessage() {
    const content = messageInput.value.trim();
    if (!content || isAwaitingResponse) return;
    
    // Hide welcome screen
    welcomeScreen.classList.add('hidden');
    messagesArea.classList.add('active');
    
    // Create new chat if needed
    if (!currentChatId) {
        const newChat = {
            id: generateId(),
            title: content.substring(0, 50) + (content.length > 50 ? '...' : ''),
            messages: [],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };
        chats.unshift(newChat);
        currentChatId = newChat.id;
        persistActiveChatId(currentChatId);
    }
    
    // Add user message
    const userMessage = {
        role: 'user',
        content: content,
        timestamp: new Date().toISOString()
    };
    
    const chat = chats.find(c => c.id === currentChatId);
    chat.messages.push(userMessage);
    chat.updatedAt = userMessage.timestamp;
    
    // Render user message
    messagesArea.insertAdjacentHTML('beforeend', createMessageHTML(userMessage));
    
    // Clear input
    messageInput.value = '';
    autoResize();
    
    // Scroll to bottom
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    // Save
    saveChats();
    renderChatHistory();
    
    // Show typing indicator and get response
    showTypingIndicator();
    getBotResponse(content);
}

// Show typing indicator
function showTypingIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'message bot';
    indicator.id = 'typingIndicator';
    indicator.innerHTML = `
        <div class="message-avatar">AI</div>
        <div class="message-content">
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    messagesArea.appendChild(indicator);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Hide typing indicator
function hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.remove();
    }
}

// ── Xianxia particle burst helpers ──
let _xpLastSpawn = 0;

function getLastCharRect(el) {
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let last = null;
    let node;
    while ((node = walker.nextNode())) {
        if (node.textContent.trim()) last = node;
    }
    if (!last) return null;
    const range = document.createRange();
    const len = last.textContent.length;
    range.setStart(last, Math.max(0, len - 1));
    range.setEnd(last, len);
    const r = range.getBoundingClientRect();
    if (!r.width && !r.height) return null;
    return { x: r.right, y: r.top + r.height * 0.5 };
}

function spawnXianxiaParticles(contentEl) {
    if (!settings.xianxiaEffect) return;
    const now = Date.now();
    if (now - _xpLastSpawn < 65) return;
    _xpLastSpawn = now;

    const pos = getLastCharRect(contentEl);
    if (!pos) return;

    const GOLD = ['#f5c842', '#fbbf24', '#e8a020'];
    const JADE = ['#34d399', '#2aaa74', '#6ee7b7'];
    const WHITE = ['#ffffff', '#e0f0ff'];
    const palette = [...GOLD, ...GOLD, ...JADE, ...WHITE];

    const count = 6 + (Math.random() * 4 | 0);
    for (let i = 0; i < count; i++) {
        const isSpark = Math.random() > 0.55;
        const color = palette[Math.random() * palette.length | 0];
        const angle = Math.random() * Math.PI * 2;
        const speed = 22 + Math.random() * 58;
        const dx = Math.cos(angle) * speed;
        const dy = Math.sin(angle) * speed - 10;
        const dur = (0.38 + Math.random() * 0.32).toFixed(2);
        const w = isSpark ? 2 : (2 + Math.random() * 4 | 0);
        const h = isSpark ? (5 + Math.random() * 6 | 0) : w;
        const rot = isSpark ? `${Math.atan2(dy, dx) * 180 / Math.PI + 90}deg` : '0deg';

        const p = document.createElement('div');
        p.className = 'xianxia-particle' + (isSpark ? ' spark' : '');
        p.style.cssText =
            `left:${pos.x}px;top:${pos.y}px;` +
            `width:${w}px;height:${h}px;` +
            `background:${color};` +
            `box-shadow:0 0 5px ${color},0 0 10px ${color};` +
            `--pdx:${dx}px;--pdy:${dy}px;--pdur:${dur}s;` +
            `transform:rotate(${rot});` +
            `margin-left:-${w/2}px;margin-top:-${h/2}px;`;
        document.body.appendChild(p);
        p.addEventListener('animationend', () => p.remove(), { once: true });
    }

    // Ring pulse
    const ring = document.createElement('div');
    ring.className = 'xianxia-ring';
    ring.style.cssText = `left:${pos.x}px;top:${pos.y}px;`;
    document.body.appendChild(ring);
    ring.addEventListener('animationend', () => ring.remove(), { once: true });
}

// Apply xianxia character-seal animation to a rendered bot message element
function applyXianxiaEffect(container) {
    if (!settings.xianxiaEffect) return;

    const MAX_CHARS = 700;
    const CHAR_DELAY_MS = 7;
    const ANIM_DURATION_MS = 900;

    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    const textNodes = [];
    let node;
    while ((node = walker.nextNode())) textNodes.push(node);

    let charIndex = 0;
    for (const textNode of textNodes) {
        const text = textNode.textContent;
        if (!text.trim() || charIndex >= MAX_CHARS) break;
        const frag = document.createDocumentFragment();
        for (let i = 0; i < text.length; i++) {
            if (charIndex >= MAX_CHARS) {
                frag.appendChild(document.createTextNode(text.slice(i)));
                break;
            }
            const span = document.createElement('span');
            span.className = 'xianxia-char';
            span.style.animationDelay = `${charIndex * CHAR_DELAY_MS}ms`;
            span.textContent = text[i];
            frag.appendChild(span);
            charIndex++;
        }
        textNode.parentNode.replaceChild(frag, textNode);
    }

    const cleanup = charIndex * CHAR_DELAY_MS + ANIM_DURATION_MS + 200;
    setTimeout(() => {
        container.querySelectorAll('.xianxia-char').forEach(span => {
            if (span.parentNode) span.parentNode.replaceChild(document.createTextNode(span.textContent), span);
        });
        container.normalize();
    }, cleanup);
}

async function getBotResponse(userMessage) {
    isAwaitingResponse = true;
    sendBtn.disabled = true;

    let placeholder = null;
    let accumulated = '';
    let sources = [];
    let errorMessage = null;
    let lowConfidence = false;
    let regenerated = false;

    const ensurePlaceholder = () => {
        if (placeholder) return placeholder;
        hideTypingIndicator();
        const botMessage = {
            role: 'bot',
            content: '',
            timestamp: new Date().toISOString(),
        };
        const wrapper = document.createElement('div');
        wrapper.innerHTML = createMessageHTML(botMessage);
        placeholder = wrapper.firstElementChild;
        messagesArea.appendChild(placeholder);
        if (settings.xianxiaEffect) placeholder.classList.add('xianxia-streaming');
        return placeholder;
    };

    const isNearBottom = () => {
        const slack = 80;
        return chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < slack;
    };

    const renderInto = (text) => {
        const target = ensurePlaceholder();
        const contentEl = target.querySelector('.message-markdown')
            || target.querySelector('.message-content p')
            || target.querySelector('.message-content');
        const wasAtBottom = isNearBottom();
        if (contentEl) {
            contentEl.innerHTML = formatMessageBody(text);
            spawnXianxiaParticles(contentEl);
        }
        if (wasAtBottom) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    };

    try {
        const history = buildRequestHistory();
        const response = await fetch(chatApiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: userMessage,
                history,
                session_id: currentChatId,
            }),
        });

        if (!response.ok || !response.body) {
            const fallback = await response.json().catch(() => ({}));
            throw new Error(fallback.error || `HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split('\n\n');
            buffer = parts.pop() || '';

            for (const part of parts) {
                const line = part.trim();
                if (!line.startsWith('data:')) continue;
                const payload = line.slice(5).trim();
                if (!payload) continue;
                let event;
                try {
                    event = JSON.parse(payload);
                } catch (_) {
                    continue;
                }
                if (event.regenerating) {
                    regenerated = true;
                    accumulated = '';
                    renderInto('_Đang viết lại với độ chính xác cao hơn…_');
                    continue;
                }
                if (event.low_confidence) {
                    lowConfidence = true;
                    continue;
                }
                if (event.token) {
                    accumulated += event.token;
                    renderInto(accumulated);
                }
                if (event.sources) sources = event.sources;
                if (event.error) errorMessage = event.error;
                if (event.done) break;
            }
        }

        if (errorMessage && !accumulated) {
            throw new Error(errorMessage);
        }

        let finalContent = accumulated.trim() || 'Empty response.';
        if (lowConfidence) {
            finalContent += '\n\n> ⚠️ **Lưu ý:** câu trả lời này có độ tin cậy thấp so với dữ liệu trong kho. Vui lòng đối chiếu thêm với nhân viên hoặc trang sản phẩm.';
        }
        renderInto(finalContent);
        if (placeholder) {
            placeholder.classList.remove('xianxia-streaming');
            const contentEl = placeholder.querySelector('.message-markdown');
            if (contentEl) applyXianxiaEffect(contentEl);
        }

        const chat = chats.find(c => c.id === currentChatId);
        if (chat) {
            chat.messages.push({
                role: 'bot',
                content: finalContent,
                timestamp: new Date().toISOString(),
                sources,
            });
            chat.updatedAt = chat.messages[chat.messages.length - 1].timestamp;
            saveChats();
            renderChatHistory();
        }
    } catch (error) {
        const text = `Sorry, the chatbot could not answer right now.\n\n${error.message}`;
        renderInto(text);
        const chat = chats.find(c => c.id === currentChatId);
        if (chat) {
            chat.messages.push({
                role: 'bot',
                content: text,
                timestamp: new Date().toISOString(),
            });
            chat.updatedAt = chat.messages[chat.messages.length - 1].timestamp;
            saveChats();
            renderChatHistory();
        }
    } finally {
        if (placeholder) placeholder.classList.remove('xianxia-streaming');
        hideTypingIndicator();
        isAwaitingResponse = false;
        sendBtn.disabled = false;
    }
}

function extractBotContent(data) {
    if (typeof data.answer === 'string' && data.answer.trim()) {
        return data.answer.trim();
    }

    if (Array.isArray(data.sources) && data.sources.length > 0) {
        return data.sources.join('\n');
    }

    if (typeof data.error === 'string' && data.error.trim()) {
        return data.error.trim();
    }

    return 'The chatbot returned an empty response.';
}

// Copy message
function copyMessage(btn) {
    const messageContent = btn.closest('.message-content');
    const contentEl = messageContent.querySelector('.message-markdown')
        || messageContent.querySelector('p');
    const content = contentEl ? contentEl.innerText : '';
    navigator.clipboard.writeText(content).then(() => {
        showToast('Copied to clipboard', 'success');
    });
}

// Show delete confirmation
function showDeleteConfirmation(chatId) {
    deleteTargetId = chatId;
    deleteModal.classList.add('active');
}

// Hide delete modal
function hideDeleteModal() {
    deleteTargetId = null;
    deleteModal.classList.remove('active');
}

// Delete chat
async function deleteChat(chatId) {
    chats = chats.filter(c => c.id !== chatId);
    localStorage.setItem('techChatHistory', JSON.stringify(chats));
    await deleteServerChat(chatId);
    renderChatHistory();
    
    if (currentChatId === chatId) {
        persistActiveChatId(null);
        startNewChat();
    }
    
    showToast('Conversation deleted', 'success');
}

async function deleteServerChat(chatId) {
    if (!chatHistoryUrl) return;

    try {
        const response = await fetch(`${chatHistoryUrl}${encodeURIComponent(chatId)}/`, {
            method: 'DELETE',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': getCsrfToken() },
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
    } catch (error) {
        showToast('Could not delete server history.', 'error');
    }
}

async function clearServerHistory() {
    if (!chatHistoryClearUrl) return;

    try {
        const response = await fetch(chatHistoryClearUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': getCsrfToken() },
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
    } catch (error) {
        showToast('Could not clear server history.', 'error');
    }
}

// Export data
function exportData() {
    const data = {
        chats: chats,
        settings: settings,
        exportedAt: new Date().toISOString()
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `tech-chatbot-export-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    
    URL.revokeObjectURL(url);
    showToast('Data exported', 'success');
}

// Show toast notification
function showToast(message, type = 'info') {
    // Remove existing toast
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Show toast
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Hide toast
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Show overlay (for mobile)
function showOverlay() {
    let overlay = document.querySelector('.sidebar-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        overlay.addEventListener('click', () => {
            sidebar.classList.remove('mobile-open');
            hideOverlay();
        });
        document.body.appendChild(overlay);
    }
    overlay.classList.add('active');
}

// Hide overlay
function hideOverlay() {
    const overlay = document.querySelector('.sidebar-overlay');
    if (overlay) {
        overlay.classList.remove('active');
    }
}

// Generate unique ID
function generateId() {
    return 'chat_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Make copyMessage available globally
window.copyMessage = copyMessage;

// Initialize app
document.addEventListener('DOMContentLoaded', init);

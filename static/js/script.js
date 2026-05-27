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
const clearHistoryBtn = document.getElementById('clearHistoryBtn');
const exportDataBtn = document.getElementById('exportDataBtn');
const todayHistory = document.getElementById('todayHistory');
const weekHistory = document.getElementById('weekHistory');
const monthHistory = document.getElementById('monthHistory');
const mainContent = document.getElementById('mainContent');
const chatApiUrl = mainContent?.dataset.chatApiUrl || '/message/';

// State
let currentChatId = null;
let chats = [];
let isAwaitingResponse = false;
let settings = {
    darkMode: false,
    fontSize: 'medium',
    saveHistory: true,
    enterSend: true
};
let deleteTargetId = null;

// Initialize
function init() {
    loadSettings();
    loadChats();
    applySettings();
    renderChatHistory();
    setupEventListeners();
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
}

// Load chats from localStorage
function loadChats() {
    const savedChats = localStorage.getItem('techChatHistory');
    if (savedChats) {
        chats = JSON.parse(savedChats);
    }
}

// Save chats to localStorage
function saveChats() {
    if (settings.saveHistory) {
        localStorage.setItem('techChatHistory', JSON.stringify(chats));
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
    
    chats.forEach(chat => {
        const chatDate = new Date(chat.createdAt);
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
    
    clearHistoryBtn.addEventListener('click', () => {
        if (confirm('Are you sure you want to clear all chat history?')) {
            chats = [];
            localStorage.removeItem('techChatHistory');
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
    return `<p>${formatMessageBody(content)}</p>`;
}

function formatMessageBody(content) {
    // Escape HTML first
    let formatted = escapeHtml(content || '');
    
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
    
    // Line breaks
    formatted = formatted.replace(/\n/g, '<br>');
    
    return formatted;
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
            createdAt: new Date().toISOString()
        };
        chats.unshift(newChat);
        currentChatId = newChat.id;
    }
    
    // Add user message
    const userMessage = {
        role: 'user',
        content: content,
        timestamp: new Date().toISOString()
    };
    
    const chat = chats.find(c => c.id === currentChatId);
    chat.messages.push(userMessage);
    
    // Render user message
    messagesArea.innerHTML += createMessageHTML(userMessage);
    
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

async function getBotResponse(userMessage) {
    isAwaitingResponse = true;
    sendBtn.disabled = true;

    let placeholder = null;
    let accumulated = '';
    let sources = [];
    let errorMessage = null;

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
        return placeholder;
    };

    const renderInto = (text) => {
        const target = ensurePlaceholder();
        const contentEl = target.querySelector('.message-content p')
            || target.querySelector('.message-content');
        if (contentEl) contentEl.innerHTML = formatMessageBody(text);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    };

    try {
        const response = await fetch(chatApiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: userMessage }),
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

        const finalContent = accumulated.trim() || 'Empty response.';
        renderInto(finalContent);

        const chat = chats.find(c => c.id === currentChatId);
        if (chat) {
            chat.messages.push({
                role: 'bot',
                content: finalContent,
                timestamp: new Date().toISOString(),
                sources,
            });
            saveChats();
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
            saveChats();
        }
    } finally {
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
    const content = btn.closest('.message-content').querySelector('p').textContent;
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
function deleteChat(chatId) {
    chats = chats.filter(c => c.id !== chatId);
    saveChats();
    renderChatHistory();
    
    if (currentChatId === chatId) {
        startNewChat();
    }
    
    showToast('Conversation deleted', 'success');
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

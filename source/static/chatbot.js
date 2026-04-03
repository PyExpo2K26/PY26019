(function () {
    function appendMessage(container, role, text) {
        if (!container) return;
        const bubble = document.createElement('div');
        bubble.style.maxWidth = '85%';
        bubble.style.marginBottom = '12px';
        bubble.style.padding = '12px 14px';
        bubble.style.borderRadius = '14px';
        bubble.style.lineHeight = '1.5';
        bubble.style.whiteSpace = 'pre-wrap';
        bubble.style.fontSize = '14px';
        bubble.style.boxShadow = '0 4px 12px rgba(15,76,129,.06)';
        if (role === 'user') {
            bubble.style.marginLeft = 'auto';
            bubble.style.background = 'linear-gradient(135deg, #0f4c81, #2563eb)';
            bubble.style.color = '#fff';
        } else {
            bubble.style.marginRight = 'auto';
            bubble.style.background = '#fff';
            bubble.style.color = '#16324f';
            bubble.style.border = '1px solid #cde3f5';
        }
        bubble.textContent = text;
        container.appendChild(bubble);
        container.scrollTop = container.scrollHeight;
    }

    async function sendMessage(message) {
        const container = document.getElementById('chatbot-messages');
        const input = document.getElementById('chatbot-input');
        const sendBtn = document.getElementById('chatbot-send');
        if (!container || !input || !sendBtn) return;

        const text = (message != null ? message : input.value).trim();
        if (!text) return;

        appendMessage(container, 'user', text);
        input.value = '';
        sendBtn.disabled = true;

        try {
            const context = {};
            if (window.activeLocation) {
                context.location = window.activeLocation;
            }
            const response = await fetch('/api/chatbot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, context })
            });
            const payload = await response.json();
            if (!response.ok || !payload.success) {
                throw new Error(payload.error || 'Assistant unavailable');
            }
            appendMessage(container, 'bot', payload.reply || 'No response available.');
        } catch (error) {
            appendMessage(container, 'bot', 'The assistant is temporarily unavailable. Please try again in a moment.');
        } finally {
            sendBtn.disabled = false;
            input.focus();
        }
    }

    function init() {
        const container = document.getElementById('chatbot-messages');
        const input = document.getElementById('chatbot-input');
        const sendBtn = document.getElementById('chatbot-send');
        if (!container || !input || !sendBtn) return;

        if (!container.dataset.initialized) {
            container.dataset.initialized = '1';
            appendMessage(
                container,
                'bot',
                'Ask me about weather, flood risk, forecast windows, shelters, safe routes, or rainfall scenarios.'
            );
        }

        sendBtn.addEventListener('click', function () {
            sendMessage();
        });
        input.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                sendMessage();
            }
        });

        const fab = document.getElementById('chatbot-fab');
        const panel = document.getElementById('chatbot-panel');
        const closeBtn = document.getElementById('chatbot-close');

        if (fab && panel) {
            fab.addEventListener('click', function () {
                panel.style.display = panel.style.display === 'flex' ? 'none' : 'flex';
            });
        }
        if (closeBtn && panel) {
            closeBtn.addEventListener('click', function () {
                panel.style.display = 'none';
            });
        }
    }

    window.sendQuickChatbotMessage = function (message) {
        const panel = document.getElementById('chatbot-panel');
        if (panel) panel.style.display = 'flex';
        sendMessage(message);
    };

    document.addEventListener('DOMContentLoaded', init);
})();

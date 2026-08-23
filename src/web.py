import uuid
import json
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

from src.agent.agent import SupportAgent

app = Flask(__name__)
CORS(app)

agent = SupportAgent()

# Simple session store
sessions: dict[str, str] = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aster & Row — Customer Support</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/dompurify@3.1.6/dist/purify.min.js"></script>
    <style>
        :root {
            --bg-main: #0b0f19;
            --bg-card: rgba(20, 29, 47, 0.75);
            --bg-card-hover: rgba(27, 39, 64, 0.9);
            --primary: #3b82f6;
            --primary-glow: rgba(59, 130, 246, 0.35);
            --primary-gradient: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
            --user-bubble: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
            --bot-bubble: rgba(18, 26, 43, 0.9);
            --bot-border: rgba(51, 65, 85, 0.6);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-amber: #f59e0b;
            --accent-green: #10b981;
            --border: rgba(51, 65, 85, 0.5);
            --radius-lg: 16px;
            --radius-md: 12px;
            --radius-sm: 8px;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background: radial-gradient(circle at top right, #172554 0%, #0b0f19 50%, #050811 100%);
            color: var(--text-primary);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }

        .app-container {
            width: 100%;
            max-width: 1000px;
            height: 94vh;
            margin: auto;
            background: var(--bg-card);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            display: flex;
            flex-direction: column;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6), 0 0 40px rgba(37, 99, 235, 0.1);
            overflow: hidden;
        }

        /* Header */
        .header {
            padding: 18px 28px;
            background: rgba(15, 23, 42, 0.85);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .brand-section {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .brand-logo {
            width: 42px;
            height: 42px;
            border-radius: 12px;
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            box-shadow: 0 4px 12px var(--primary-glow);
        }

        .brand-info h1 {
            font-size: 18px;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            font-weight: 500;
            color: var(--accent-green);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--accent-green);
            box-shadow: 0 0 8px var(--accent-green);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { opacity: 0.6; }
            50% { opacity: 1; }
            100% { opacity: 0.6; }
        }

        .header-actions button {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
            color: var(--text-secondary);
            padding: 8px 14px;
            border-radius: var(--radius-sm);
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            font-family: inherit;
        }

        .header-actions button:hover {
            background: rgba(255, 255, 255, 0.1);
            color: #ffffff;
            border-color: #475569;
        }

        /* Chat Container */
        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 24px 28px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            scroll-behavior: smooth;
        }

        .chat-container::-webkit-scrollbar {
            width: 6px;
        }
        .chat-container::-webkit-scrollbar-track {
            background: transparent;
        }
        .chat-container::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
        }

        /* Message Row */
        .message-row {
            display: flex;
            gap: 12px;
            max-width: 85%;
            animation: fadeIn 0.3s ease;
        }

        .message-row.user {
            align-self: flex-end;
            flex-direction: row-reverse;
        }

        .message-row.assistant {
            align-self: flex-start;
        }

        .avatar {
            width: 34px;
            height: 34px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            flex-shrink: 0;
            margin-top: 2px;
        }

        .avatar.assistant {
            background: rgba(59, 130, 246, 0.15);
            border: 1px solid rgba(59, 130, 246, 0.3);
            color: #60a5fa;
        }

        .avatar.user {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.15);
            color: #e2e8f0;
        }

        .message-content-wrapper {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .message-bubble {
            padding: 14px 18px;
            border-radius: var(--radius-lg);
            font-size: 14.5px;
            line-height: 1.6;
            letter-spacing: -0.01em;
            word-break: break-word;
        }

        .message-row.user .message-bubble {
            background: var(--user-bubble);
            color: #ffffff;
            border-bottom-right-radius: 4px;
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.25);
        }

        .message-row.assistant .message-bubble {
            background: var(--bot-bubble);
            color: #f1f5f9;
            border: 1px solid var(--bot-border);
            border-bottom-left-radius: 4px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
        }

        /* Rich Typography Inside Messages */
        .message-bubble p {
            margin-bottom: 10px;
        }
        .message-bubble p:last-child {
            margin-bottom: 0;
        }

        .message-bubble strong {
            font-weight: 600;
            color: #ffffff;
        }

        .message-bubble ul, .message-bubble ol {
            margin: 8px 0 10px 20px;
        }

        .message-bubble li {
            margin-bottom: 6px;
        }

        .message-bubble li:last-child {
            margin-bottom: 0;
        }

        .message-bubble code {
            font-family: monospace;
            background: rgba(0, 0, 0, 0.3);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 13px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        /* Source Badge Styling */
        .source-pill {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            font-size: 11px;
            font-weight: 500;
            color: #93c5fd;
            background: rgba(59, 130, 246, 0.12);
            border: 1px solid rgba(59, 130, 246, 0.25);
            padding: 2px 8px;
            border-radius: 6px;
            margin: 3px 4px 3px 0;
            vertical-align: baseline;
            white-space: nowrap;
        }

        .source-pill::before {
            content: "📄";
            font-size: 10px;
        }

        /* Handoff Contact Card */
        .handoff-card {
            margin-top: 10px;
            padding: 12px 14px;
            background: rgba(245, 158, 11, 0.08);
            border: 1px solid rgba(245, 158, 11, 0.25);
            border-radius: var(--radius-md);
            font-size: 13.5px;
            color: #fde68a;
            display: flex;
            align-items: flex-start;
            gap: 10px;
        }

        .handoff-icon {
            font-size: 18px;
            line-height: 1;
        }

        .handoff-details {
            flex: 1;
        }

        .handoff-details a {
            color: #60a5fa;
            text-decoration: underline;
            text-underline-offset: 2px;
        }

        .message-time {
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 2px;
            padding: 0 4px;
        }

        .message-row.user .message-time {
            text-align: right;
        }

        /* Quick Suggestions */
        .suggestions-bar {
            display: flex;
            gap: 8px;
            padding: 8px 28px;
            overflow-x: auto;
            background: rgba(15, 23, 42, 0.5);
            border-top: 1px solid rgba(51, 65, 85, 0.3);
        }

        .suggestions-bar::-webkit-scrollbar {
            display: none;
        }

        .chip {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border);
            color: var(--text-secondary);
            font-size: 12.5px;
            font-weight: 500;
            padding: 6px 14px;
            border-radius: 20px;
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.2s ease;
            font-family: inherit;
        }

        .chip:hover {
            background: rgba(59, 130, 246, 0.15);
            border-color: rgba(59, 130, 246, 0.4);
            color: #93c5fd;
            transform: translateY(-1px);
        }

        /* Typing Indicator */
        .typing-indicator {
            display: none;
            align-self: flex-start;
            margin-left: 46px;
            padding: 10px 16px;
            background: var(--bot-bubble);
            border: 1px solid var(--bot-border);
            border-radius: 12px;
            color: var(--text-secondary);
            font-size: 13px;
            align-items: center;
            gap: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }

        .typing-indicator.visible {
            display: flex;
            animation: fadeIn 0.2s ease;
        }

        .dots {
            display: flex;
            gap: 4px;
        }

        .dot {
            width: 6px;
            height: 6px;
            background: #60a5fa;
            border-radius: 50%;
            animation: bounce 1.4s infinite ease-in-out both;
        }

        .dot:nth-child(1) { animation-delay: -0.32s; }
        .dot:nth-child(2) { animation-delay: -0.16s; }

        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); opacity: 0.4; }
            40% { transform: scale(1); opacity: 1; }
        }

        /* Input Area */
        .input-area {
            padding: 18px 28px;
            background: rgba(15, 23, 42, 0.95);
            border-top: 1px solid var(--border);
            display: flex;
            gap: 12px;
            align-items: center;
        }

        .input-container {
            flex: 1;
            position: relative;
            display: flex;
            align-items: center;
        }

        .input-container input {
            width: 100%;
            padding: 14px 18px;
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            background: rgba(11, 15, 25, 0.8);
            color: #ffffff;
            font-family: inherit;
            font-size: 14.5px;
            outline: none;
            transition: all 0.2s ease;
        }

        .input-container input:focus {
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
            background: rgba(15, 23, 42, 0.9);
        }

        .input-container input::placeholder {
            color: #64748b;
        }

        .send-button {
            padding: 14px 24px;
            background: var(--primary-gradient);
            color: #ffffff;
            border: none;
            border-radius: var(--radius-md);
            font-family: inherit;
            font-weight: 600;
            font-size: 14.5px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 4px 12px var(--primary-glow);
        }

        .send-button:hover:not(:disabled) {
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(59, 130, 246, 0.45);
        }

        .send-button:active:not(:disabled) {
            transform: translateY(0);
        }

        .send-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            box-shadow: none;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @media (max-width: 768px) {
            .app-container {
                height: 100vh;
                border-radius: 0;
                border: none;
            }
            .header, .chat-container, .input-area, .suggestions-bar {
                padding-left: 16px;
                padding-right: 16px;
            }
            .message-row {
                max-width: 95%;
            }
        }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Header -->
        <div class="header">
            <div class="brand-section">
                <div class="brand-logo">✦</div>
                <div class="brand-info">
                    <h1>Aster & Row Support</h1>
                    <div class="status-badge">
                        <span class="status-dot"></span>
                        AI Support Assistant • Online
                    </div>
                </div>
            </div>
            <div class="header-actions">
                <button onclick="resetConversation()" title="Start a new conversation">↻ Reset Chat</button>
            </div>
        </div>

        <!-- Chat Messages -->
        <div class="chat-container" id="chat">
            <div class="message-row assistant">
                <div class="avatar assistant">✦</div>
                <div class="message-content-wrapper">
                    <div class="message-bubble">
                        Hello! I'm your Aster & Row support assistant. I can help you with product information (like our <strong>Breeze Tumbler</strong>), return & warranty policies, or look up your order status. How can I help you today?
                    </div>
                    <div class="message-time">Just now</div>
                </div>
            </div>
        </div>

        <!-- Typing Indicator -->
        <div class="typing-indicator" id="typing">
            <div class="dots">
                <div class="dot"></div>
                <div class="dot"></div>
                <div class="dot"></div>
            </div>
            <span>Consulting knowledge base...</span>
        </div>

        <!-- Suggestions Bar -->
        <div class="suggestions-bar">
            <button class="chip" onclick="useSuggestion('What is your return policy?')">📦 Return Policy</button>
            <button class="chip" onclick="useSuggestion('Tell me about the Breeze Tumbler')">🥤 Breeze Tumbler Specs</button>
            <button class="chip" onclick="useSuggestion('What are the domestic shipping options?')">🚚 Shipping Options</button>
            <button class="chip" onclick="useSuggestion('How do I clean my tumbler?')">🧼 Cleaning & Care</button>
            <button class="chip" onclick="useSuggestion('What is your warranty coverage?')">🛡️ Warranty Coverage</button>
            <button class="chip" onclick="useSuggestion('What are the TrailPlus membership benefits?')">⭐ TrailPlus Membership</button>
        </div>

        <!-- Input Area -->
        <div class="input-area">
            <div class="input-container">
                <input type="text" id="input" placeholder="Type your question or order number..." autocomplete="off" />
            </div>
            <button id="send" class="send-button" onclick="sendMessage()">
                <span>Send</span>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13"></line>
                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                </svg>
            </button>
        </div>
    </div>

    <script>
        let sessionId = crypto.randomUUID();
        const chat = document.getElementById('chat');
        const input = document.getElementById('input');
        const sendBtn = document.getElementById('send');
        const typing = document.getElementById('typing');

        // Configure marked for clean, safe output
        marked.setOptions({
            breaks: true,
            gfm: true
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !sendBtn.disabled) sendMessage();
        });

        function formatTime() {
            const now = new Date();
            return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }

        function formatMessageContent(rawText) {
            if (!rawText) return '';

            // Extract handoff note if present to style as card
            let processed = rawText;

            // Transform [Source: filename > Section] into styled badges
            processed = processed.replace(/\\[Source:\\s*([^\\]]+)\\]/g, (match, p1) => {
                return `<span class="source-pill">${p1}</span>`;
            });

            // Convert markdown to HTML
            let html = marked.parse(processed);

            // Sanitize HTML
            return DOMPurify.sanitize(html, {
                ADD_ATTR: ['target', 'class']
            });
        }

        async function sendMessage(overrideText = null) {
            const text = overrideText !== null ? overrideText : input.value.trim();
            if (!text) return;

            addMessage(text, 'user');
            if (overrideText === null) {
                input.value = '';
            }
            sendBtn.disabled = true;
            typing.classList.add('visible');
            chat.scrollTop = chat.scrollHeight;

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: text, session_id: sessionId}),
                });
                const data = await res.json();
                if (data.response) {
                    addMessage(data.response, 'assistant');
                } else {
                    addMessage('I apologize, but I could not retrieve a response. Please try again.', 'assistant');
                }
            } catch (err) {
                addMessage('Sorry, a connection error occurred. Please check that the server is active and try again.', 'assistant');
            } finally {
                sendBtn.disabled = false;
                typing.classList.remove('visible');
                input.focus();
            }
        }

        function addMessage(rawText, role) {
            const row = document.createElement('div');
            row.className = `message-row ${role}`;

            const avatar = document.createElement('div');
            avatar.className = `avatar ${role}`;
            avatar.textContent = role === 'assistant' ? '✦' : '👤';

            const wrapper = document.createElement('div');
            wrapper.className = 'message-content-wrapper';

            const bubble = document.createElement('div');
            bubble.className = 'message-bubble';
            
            if (role === 'assistant') {
                bubble.innerHTML = formatMessageContent(rawText);
            } else {
                bubble.textContent = rawText;
            }

            const time = document.createElement('div');
            time.className = 'message-time';
            time.textContent = formatTime();

            wrapper.appendChild(bubble);
            wrapper.appendChild(time);

            row.appendChild(avatar);
            row.appendChild(wrapper);

            chat.appendChild(row);
            chat.scrollTop = chat.scrollHeight;
        }

        function useSuggestion(text) {
            input.value = text;
            sendMessage(text);
        }

        async function resetConversation() {
            if (!confirm('Start a new support conversation?')) return;
            try {
                await fetch('/api/reset', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({session_id: sessionId})
                });
            } catch (e) {}
            
            sessionId = crypto.randomUUID();
            chat.innerHTML = `
                <div class="message-row assistant">
                    <div class="avatar assistant">✦</div>
                    <div class="message-content-wrapper">
                        <div class="message-bubble">
                            Conversation restarted. How can I help you today with Aster & Row products or orders?
                        </div>
                        <div class="message-time">${formatTime()}</div>
                    </div>
                </div>
            `;
        }
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/chat", methods=["POST"])
def chat_endpoint():
    data = request.get_json()
    
    if not data or "message" not in data:
        return jsonify({"error": "Missing 'message' field"}), 400
    
    message = data["message"]
    session_id = data.get("session_id", str(uuid.uuid4()))
    
    response = agent.chat(message, session_id)
    
    # Get trace for debug purposes
    trace = agent.get_last_trace()
    
    return jsonify({
        "response": response,
        "session_id": session_id,
        "trace": trace if request.args.get("debug") else None,
    })


@app.route("/api/reset", methods=["POST"])
def reset_endpoint():
    data = request.get_json() or {}
    session_id = data.get("session_id", "default")
    agent.reset_session(session_id)
    return jsonify({"status": "ok"})


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Aster & Row Support Agent Web Server")
    parser.add_argument("--port", type=int, default=5000, help="Port to run on")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    args = parser.parse_args()
    
    app.run(host="0.0.0.0", port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()


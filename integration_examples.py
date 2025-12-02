"""
Frontend Integration Guide
===========================
Examples for integrating with the LangGraph API Wrapper

This file contains:
1. JavaScript/TypeScript client examples
2. REST API usage examples
3. WebSocket integration examples
4. Error handling patterns
"""

# ============================================================================
# 1. JAVASCRIPT/TYPESCRIPT CLIENT
# ============================================================================

JAVASCRIPT_CLIENT = """
// api-client.js - REST API Client

class LangGraphClient {
    constructor(baseURL = 'http://localhost:8000', apiKey = null) {
        this.baseURL = baseURL;
        this.apiKey = apiKey;
    }

    /**
     * Send a chat message (non-streaming)
     */
    async chat(message, options = {}) {
        const response = await fetch(`${this.baseURL}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(this.apiKey && { 'X-API-Key': this.apiKey })
            },
            body: JSON.stringify({
                message,
                session_id: options.sessionId || null,
                context: options.context || {},
                stream: false
            })
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        return await response.json();
    }

    /**
     * Check service health
     */
    async health() {
        const response = await fetch(`${this.baseURL}/health`);
        return await response.json();
    }

    /**
     * Get available capabilities
     */
    async getCapabilities() {
        const response = await fetch(`${this.baseURL}/api/capabilities`);
        return await response.json();
    }

    /**
     * Get session information
     */
    async getSession(sessionId) {
        const response = await fetch(`${this.baseURL}/api/sessions/${sessionId}`);
        return await response.json();
    }

    /**
     * Delete a session
     */
    async deleteSession(sessionId) {
        const response = await fetch(`${this.baseURL}/api/sessions/${sessionId}`, {
            method: 'DELETE'
        });
        return await response.json();
    }
}

// Usage Example
const client = new LangGraphClient('http://localhost:8000');

// Simple chat
client.chat('Show me all pods in CrashLoopBackOff')
    .then(response => {
        console.log('Response:', response.response);
        console.log('Forward links:', response.forward_links);
    })
    .catch(error => console.error('Error:', error));

// With context
client.chat('Show me recent incidents', {
    sessionId: 'user-123',
    context: { namespace: 'production', severity: 'high' }
})
    .then(response => console.log(response));
"""


TYPESCRIPT_CLIENT = """
// api-client.ts - TypeScript REST API Client

interface ChatRequest {
    message: string;
    session_id?: string;
    context?: Record<string, any>;
    stream?: boolean;
}

interface ChatResponse {
    response: string;
    session_id: string;
    timestamp: string;
    metadata?: {
        tools_used?: string[];
        query_type?: string;
    };
    forward_links?: string[];
}

interface HealthResponse {
    status: string;
    version: string;
    timestamp: string;
    services: Record<string, string>;
}

class LangGraphClient {
    private baseURL: string;
    private apiKey: string | null;

    constructor(baseURL: string = 'http://localhost:8000', apiKey: string | null = null) {
        this.baseURL = baseURL;
        this.apiKey = apiKey;
    }

    async chat(message: string, options: {
        sessionId?: string;
        context?: Record<string, any>;
    } = {}): Promise<ChatResponse> {
        const response = await fetch(`${this.baseURL}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(this.apiKey && { 'X-API-Key': this.apiKey })
            },
            body: JSON.stringify({
                message,
                session_id: options.sessionId || null,
                context: options.context || {},
                stream: false
            })
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        return await response.json();
    }

    async health(): Promise<HealthResponse> {
        const response = await fetch(`${this.baseURL}/health`);
        return await response.json();
    }

    async getCapabilities() {
        const response = await fetch(`${this.baseURL}/api/capabilities`);
        return await response.json();
    }
}

export { LangGraphClient };
export type { ChatRequest, ChatResponse, HealthResponse };
"""


WEBSOCKET_CLIENT = """
// websocket-client.ts - WebSocket Streaming Client

class LangGraphWebSocketClient {
    private ws: WebSocket | null = null;
    private sessionId: string;
    private messageHandlers: Map<string, (data: any) => void>;

    constructor(
        private url: string = 'ws://localhost:8000/ws',
        sessionId?: string
    ) {
        this.sessionId = sessionId || `session-${Date.now()}`;
        this.messageHandlers = new Map();
    }

    /**
     * Connect to WebSocket server
     */
    connect(): Promise<void> {
        return new Promise((resolve, reject) => {
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                // Send initialization message
                this.ws!.send(JSON.stringify({
                    uuid: this.sessionId,
                    init: true
                }));
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);

                // Handle connection confirmation
                if (data.status === 'connected') {
                    console.log('Connected:', data.session_id);
                    resolve();
                    return;
                }

                // Dispatch to handlers
                if (data.on_chat_model_stream) {
                    this.emit('stream', data.on_chat_model_stream);
                } else if (data.on_tool_call) {
                    this.emit('tool_call', data.on_tool_call);
                } else if (data.on_chat_model_end) {
                    this.emit('complete', data.metadata);
                } else if (data.error) {
                    this.emit('error', data);
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                reject(error);
            };

            this.ws.onclose = () => {
                console.log('WebSocket closed');
                this.emit('close', null);
            };
        });
    }

    /**
     * Send a message
     */
    sendMessage(message: string) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            throw new Error('WebSocket not connected');
        }

        this.ws.send(JSON.stringify({
            uuid: this.sessionId,
            message,
            init: false
        }));
    }

    /**
     * Register event handler
     */
    on(event: string, handler: (data: any) => void) {
        this.messageHandlers.set(event, handler);
    }

    /**
     * Emit event to handler
     */
    private emit(event: string, data: any) {
        const handler = this.messageHandlers.get(event);
        if (handler) {
            handler(data);
        }
    }

    /**
     * Disconnect
     */
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// Usage Example
const wsClient = new LangGraphWebSocketClient('ws://localhost:8000/ws');

// Register handlers
wsClient.on('stream', (token) => {
    process.stdout.write(token); // Stream tokens as they arrive
});

wsClient.on('tool_call', (tools) => {
    console.log('\\nExecuting tools:', tools);
});

wsClient.on('complete', (metadata) => {
    console.log('\\n\\nResponse complete');
    console.log('Forward links:', metadata?.forward_links);
});

wsClient.on('error', (error) => {
    console.error('Error:', error);
});

// Connect and send message
wsClient.connect().then(() => {
    wsClient.sendMessage('Show me all pods in CrashLoopBackOff');
});
"""


REACT_INTEGRATION = """
// React Hook for LangGraph API

import { useState, useEffect, useCallback, useRef } from 'react';

interface Message {
    user: 'User' | 'Bot';
    msg: string;
}

export const useLangGraphChat = (wsUrl: string = 'ws://localhost:8000/ws') => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [isConnected, setIsConnected] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [toolCalls, setToolCalls] = useState<string[]>([]);
    const [currentResponse, setCurrentResponse] = useState('');
    
    const wsRef = useRef<WebSocket | null>(null);
    const sessionId = useRef(`session-${Date.now()}`);

    // Connect to WebSocket
    useEffect(() => {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            ws.send(JSON.stringify({
                uuid: sessionId.current,
                init: true
            }));
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.status === 'connected') {
                setIsConnected(true);
                return;
            }

            if (data.on_tool_call) {
                setToolCalls(data.on_tool_call.tools || []);
            }

            if (data.on_chat_model_stream) {
                setCurrentResponse(prev => prev + data.on_chat_model_stream);
            }

            if (data.on_chat_model_end) {
                // Add complete response to messages
                setMessages(prev => {
                    const lastMsg = prev[prev.length - 1];
                    if (lastMsg?.user === 'Bot') {
                        lastMsg.msg = currentResponse;
                        return [...prev];
                    }
                    return [...prev, { user: 'Bot', msg: currentResponse }];
                });
                setCurrentResponse('');
                setToolCalls([]);
                setIsLoading(false);
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            setIsConnected(false);
        };

        ws.onclose = () => {
            setIsConnected(false);
        };

        return () => {
            ws.close();
        };
    }, [wsUrl]);

    // Send message
    const sendMessage = useCallback((message: string) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            console.error('WebSocket not connected');
            return;
        }

        // Add user message
        setMessages(prev => [...prev, { user: 'User', msg: message }]);
        setIsLoading(true);
        setCurrentResponse('');

        // Send to server
        wsRef.current.send(JSON.stringify({
            uuid: sessionId.current,
            message,
            init: false
        }));
    }, []);

    return {
        messages,
        isConnected,
        isLoading,
        toolCalls,
        sendMessage
    };
};

// Usage in React Component
const ChatComponent = () => {
    const { messages, isConnected, isLoading, toolCalls, sendMessage } = useLangGraphChat();
    const [input, setInput] = useState('');

    const handleSend = () => {
        if (input.trim()) {
            sendMessage(input);
            setInput('');
        }
    };

    return (
        <div className="chat-container">
            <div className="connection-status">
                {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
            </div>

            <div className="messages">
                {messages.map((msg, idx) => (
                    <div key={idx} className={`message ${msg.user}`}>
                        {msg.msg}
                    </div>
                ))}
                {isLoading && <div className="loading">Thinking...</div>}
                {toolCalls.length > 0 && (
                    <div className="tool-indicator">
                        Using tools: {toolCalls.join(', ')}
                    </div>
                )}
            </div>

            <div className="input-container">
                <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                    placeholder="Type your message..."
                />
                <button onClick={handleSend}>Send</button>
            </div>
        </div>
    );
};
"""


# ============================================================================
# 2. CURL EXAMPLES (For Testing)
# ============================================================================

CURL_EXAMPLES = """
# ============================================================================
# CURL Examples for Testing API
# ============================================================================

# Health Check
curl -X GET http://localhost:8000/health

# Get Capabilities
curl -X GET http://localhost:8000/api/capabilities

# Simple Chat (REST)
curl -X POST http://localhost:8000/api/chat \\
  -H "Content-Type: application/json" \\
  -d '{
    "message": "Show me all pods in CrashLoopBackOff",
    "session_id": "test-session-123",
    "stream": false
  }'

# Chat with Context
curl -X POST http://localhost:8000/api/chat \\
  -H "Content-Type: application/json" \\
  -d '{
    "message": "Show me recent incidents",
    "session_id": "test-session-123",
    "context": {
      "namespace": "production",
      "severity": "high"
    },
    "stream": false
  }'

# Chat with API Key
curl -X POST http://localhost:8000/api/chat \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: your-api-key-here" \\
  -d '{
    "message": "Show me all tickets",
    "stream": false
  }'

# Get Session Info
curl -X GET http://localhost:8000/api/sessions/test-session-123

# Delete Session
curl -X DELETE http://localhost:8000/api/sessions/test-session-123

# Get API Documentation (OpenAPI)
curl -X GET http://localhost:8000/api/openapi.json

# Access Interactive Docs
# Open in browser: http://localhost:8000/api/docs
"""


# ============================================================================
# 3. PYTHON CLIENT EXAMPLE
# ============================================================================

PYTHON_CLIENT = '''
"""Python client for LangGraph API"""

import requests
from typing import Optional, Dict, Any

class LangGraphClient:
    """Python client for LangGraph API"""
    
    def __init__(self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers["X-API-Key"] = api_key
    
    def chat(self, message: str, session_id: Optional[str] = None, 
             context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a chat message"""
        response = self.session.post(
            f"{self.base_url}/api/chat",
            json={
                "message": message,
                "session_id": session_id,
                "context": context or {},
                "stream": False
            }
        )
        response.raise_for_status()
        return response.json()
    
    def health(self) -> Dict[str, Any]:
        """Check service health"""
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get available capabilities"""
        response = self.session.get(f"{self.base_url}/api/capabilities")
        response.raise_for_status()
        return response.json()

# Usage
client = LangGraphClient("http://localhost:8000")
response = client.chat("Show me all pods in CrashLoopBackOff")
print(response["response"])
print("Forward links:", response.get("forward_links"))
'''


if __name__ == "__main__":
    print("=" * 80)
    print("FRONTEND INTEGRATION EXAMPLES")
    print("=" * 80)
    print()
    print("1. JavaScript Client:")
    print("-" * 80)
    print(JAVASCRIPT_CLIENT)
    print()
    print("2. TypeScript Client:")
    print("-" * 80)
    print(TYPESCRIPT_CLIENT)
    print()
    print("3. WebSocket Client:")
    print("-" * 80)
    print(WEBSOCKET_CLIENT)
    print()
    print("4. React Integration:")
    print("-" * 80)
    print(REACT_INTEGRATION)
    print()
    print("5. CURL Examples:")
    print("-" * 80)
    print(CURL_EXAMPLES)
    print()
    print("6. Python Client:")
    print("-" * 80)
    print(PYTHON_CLIENT)

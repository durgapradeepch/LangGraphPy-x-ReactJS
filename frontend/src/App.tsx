import React, { useState, useEffect, ChangeEvent, KeyboardEvent, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { useWebSocket } from './services/useWebSocket'; // Custom hook to manage WebSocket connection
import EE from './components/easter_egg/ee'; // Easter egg component
import './App.css';

interface Message {
    user: string;
    msg: string;
    rating?: number;
}

interface ChatHistory {
    id: string;
    title: string;
    timestamp: Date;
    messages: Message[];
}

const App: React.FC = () => {
    const [messages, setMessages] = useState<Message[]>([
        { user: 'Bot', msg: 'Welcome! How can I help you today?' } // Initial bot message
    ]);
    const [input, setInput] = useState(''); // User input state
    const [showEE, setShowEE] = useState(false); // Toggle for Easter egg component
    const [chatHistories, setChatHistories] = useState<ChatHistory[]>([]);
    const [currentChatId, setCurrentChatId] = useState<string | null>(null);

    // WebSocket connection logic (message handling & status tracking)
    const { response, isOpen, toolCalls, sendMessage } = useWebSocket('ws://localhost:8000/ws', setShowEE);
    const messagesEndRef = useRef<HTMLDivElement>(null); // Ref for scrolling to the latest message

    useEffect(() => {
        // Handle WebSocket responses and update messages
        if (response) {
            console.log('📝 Updating UI with response:', response.substring(0, 100) + '...');
            setMessages((prevMessages) => {
                const lastMessage = prevMessages[prevMessages.length - 1];
                // Update last bot message or add a new one
                if (lastMessage && lastMessage.user === 'Bot') {
                    console.log('📝 Updating existing bot message');
                    lastMessage.msg = response;
                    return [...prevMessages];
                } else {
                    console.log('📝 Adding new bot message');
                    return [...prevMessages, { user: 'Bot', msg: response }];
                }
            });
        }
    }, [response]);

    // Updates input field on change
    const handleChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
        setInput(event.target.value);
    };

    // Handles sending of messages from the user
    const handleSubmit = () => {
        if (input.trim()) {
            const userMessage = { user: 'User', msg: input };
            setMessages((prevMessages) => [...prevMessages, userMessage]); // Add user message to list
            setInput('');

            if (isOpen) {
                sendMessage(input); // Send message via WebSocket if open
            }
        }
    };

    // Handle rating a bot message
    const handleRating = (messageIndex: number, rating: number) => {
        setMessages((prevMessages) => {
            const updated = [...prevMessages];
            if (updated[messageIndex].user === 'Bot') {
                updated[messageIndex].rating = rating;
            }
            return updated;
        });
    };

    // Start a new chat
    const startNewChat = () => {
        if (messages.length > 1) {
            // Save current chat to history
            const newHistory: ChatHistory = {
                id: Date.now().toString(),
                title: messages[1]?.msg.slice(0, 30) + '...' || 'New Chat',
                timestamp: new Date(),
                messages: messages
            };
            setChatHistories([newHistory, ...chatHistories]);
        }
        setMessages([{ user: 'Bot', msg: 'Welcome! How can I help you today?' }]);
        setCurrentChatId(null);
    };

    // Load a chat from history
    const loadChat = (chatId: string) => {
        const chat = chatHistories.find(c => c.id === chatId);
        if (chat) {
            setMessages(chat.messages);
            setCurrentChatId(chatId);
        }
    };

    // Delete a chat from history
    const deleteChat = (chatId: string) => {
        setChatHistories(chatHistories.filter(c => c.id !== chatId));
        if (currentChatId === chatId) {
            startNewChat();
        }
    };

    // Scrolls to the latest token in the chat whenever a new message is added
    useEffect(() => {
        const timer = setTimeout(() => {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }); // , 100); // you can add delay for scrolling, giving user a moment to read message bots message,
                       // but looks slightly jittery

        return () => clearTimeout(timer);  // Cleanup the timeout
    }, [messages]);

    // Handles "Enter" key submission without needing to click the send button
    const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault(); // Prevent default newline
            handleSubmit();
        }
    };

    return (
        <div className="App">
            <div className="sidebar">
                <div className="sidebar-header">
                    <div className="logo">🤖 Manifest Chatbot</div>
                    <button className="new-chat-btn" onClick={startNewChat}>+ New Chat</button>
                </div>
                <div className="chat-history">
                    {chatHistories.length === 0 ? (
                        <div className="no-history">No chat history yet</div>
                    ) : (
                        chatHistories.map((chat) => (
                            <div 
                                key={chat.id} 
                                className={`history-item ${currentChatId === chat.id ? 'active' : ''}`}
                                onClick={() => loadChat(chat.id)}
                            >
                                <div className="history-content">
                                    <div className="history-title">💬 {chat.title}</div>
                                    <div className="history-date">{chat.timestamp.toLocaleDateString()}</div>
                                </div>
                                <button 
                                    className="delete-btn" 
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        deleteChat(chat.id);
                                    }}
                                >
                                    🗑️
                                </button>
                            </div>
                        ))
                    )}
                </div>
                <div className="sidebar-footer">
                    <div className="made-with">Manifest</div>
                </div>
            </div>
            <div className="main-content">
                <div className="chat-container">
                    {/* Display chat messages */}
                    <div className="messages">
                        {messages.map((msg, index) => (
                            <div key={index} className={msg.user === 'User' ? 'message user-message' : 'message bot-message'}>
                                <div className="message-icon">{msg.user === 'User' ? '👤' : '🤖'}</div>
                                <div className="message-content">
                                    {msg.user === 'User' && (
                                        <>
                                            <div className="message-text">{msg.msg}</div>
                                            {/* Show tool calls right after the user's question */}
                                            {toolCalls.length > 0 && index === messages.length - 1 && (
                                                <div className="tool-call-indicator">
                                                    <div className="tool-icon">⚙️</div>
                                                    <div className="tool-text">
                                                        Using tools: {toolCalls.join(', ')}
                                                    </div>
                                                </div>
                                            )}
                                        </>
                                    )}
                                    {msg.user === 'Bot' && msg.msg && (
                                        <div className="message-text markdown-content">
                                            <ReactMarkdown>{msg.msg}</ReactMarkdown>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                        <div ref={messagesEndRef} /> {/* Reference to scroll to the latest message */}
                    </div>
                    {/* Input form for typing and sending messages */}
                    <div className="input-container">
                        <textarea
                            value={input}
                            onChange={handleChange}
                            onKeyDown={handleKeyDown}
                            placeholder="Your message"
                            rows={1}
                        />
                        <button type="button" onClick={handleSubmit} className="send-btn">➤</button>
                    </div>
                </div>
                {showEE && <EE />} {/* Easter egg component */}
            </div>
        </div>
    );
}

export default App;

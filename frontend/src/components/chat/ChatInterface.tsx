"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface ChatInterfaceProps {
  sessionId: string | null;
  onReset: () => void;
}

export default function ChatInterface({ sessionId, onReset }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hello! I'm the ET Portfolio AI. How can I help you analyze your portfolio today?"
    }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    
    // Add user message to UI
    const updatedMessages = [...messages, { role: "user" as const, content: userMessage }];
    setMessages(updatedMessages);
    setIsLoading(true);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/simple`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId || "demo-session-123",
          message: userMessage,
          history: messages.slice(1).map(m => ({ role: m.role, content: m.content })) // omit initial greeting
        }),
      });

      if (!response.ok) throw new Error("API error");

      const data = await response.json();
      
      setMessages([...updatedMessages, { role: "assistant", content: data.response }]);
    } catch (err) {
      console.error(err);
      setMessages([
        ...updatedMessages, 
        { role: "assistant", content: "Sorry, I'm having trouble connecting to the intelligence engine." }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSuggestedClick = (text: string) => {
    setInput(text);
  };

  const suggestions = [
    "Am I over-exposed to banking?",
    "Which funds overlap the most?",
    "Is my ELSS allocation optimal?"
  ];

  return (
    <div className="flex flex-col h-full bg-[#111111] border border-[#2a2a2a] rounded-lg overflow-hidden">
      <div className="bg-[#1a1a1a] p-4 border-b border-[#2a2a2a] flex justify-between items-center">
        <div>
          <h2 className="text-white font-bold tracking-tight">Portfolio Chat</h2>
          <p className="text-xs text-[#888888]">Context-aware RAG analysis over your holdings</p>
        </div>
        
        {sessionId && (
          <button 
            onClick={onReset}
            className="text-xs text-red-500 hover:text-red-400 font-medium px-2 py-1 border border-red-500/20 rounded hover:bg-red-500/10 transition-colors"
          >
            Clear Session
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div 
              className={`max-w-[80%] rounded-lg p-4 ${
                msg.role === 'user' 
                  ? 'bg-green-600 text-white shadow-md' 
                  : 'bg-[#1a1a1a] border border-[#2a2a2a] text-[#e8e8e8]'
              }`}
            >
              {msg.role === 'user' ? (
                <p className="whitespace-pre-wrap">{msg.content}</p>
              ) : (
                <div className="prose prose-invert prose-green max-w-none text-sm prose-p:leading-relaxed">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg p-4 flex gap-2">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-bounce"></div>
              <div className="w-2 h-2 rounded-full bg-green-500 animate-bounce" style={{ animationDelay: "0.2s" }}></div>
              <div className="w-2 h-2 rounded-full bg-green-500 animate-bounce" style={{ animationDelay: "0.4s" }}></div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 bg-[#1a1a1a] border-t border-[#2a2a2a]">
        {messages.length < 3 && !isLoading && (
          <div className="flex flex-wrap gap-2 mb-3">
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => handleSuggestedClick(s)}
                className="text-xs text-[#888888] bg-[#111111] border border-[#2a2a2a] hover:border-green-500/50 hover:text-white px-3 py-1.5 rounded-full transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        
        <form onSubmit={handleSubmit} className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isLoading}
            placeholder={isLoading ? "AI is typing..." : "Ask about your portfolio..."}
            className="w-full bg-[#0a0a0a] border border-[#2a2a2a] text-white px-4 py-3 rounded-lg focus:outline-none focus:border-green-500 transition-colors disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-2 px-3 py-1.5 bg-green-600 hover:bg-green-500 rounded text-sm font-bold text-white transition-colors disabled:opacity-50 disabled:bg-[#333]"
          >
            SEND
          </button>
        </form>
      </div>
    </div>
  );
}

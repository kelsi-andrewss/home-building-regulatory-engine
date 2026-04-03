import { useState, useRef, useEffect, useCallback } from 'react';
import { useAssessment } from '../context/AssessmentContext';
import { chatFollowup } from '../api/client';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: string[];
}

export default function ChatInterface() {
  const { assessment } = useAssessment();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  }, [input]);

  const sendMessage = useCallback(async () => {
    if (!input.trim() || !assessment || isStreaming) return;
    const userMsg: Message = { role: 'user', content: input.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsStreaming(true);

    const assistantMsg: Message = { role: 'assistant', content: '' };
    setMessages((prev) => [...prev, assistantMsg]);

    try {
      for await (const chunk of chatFollowup(assessment.assessment_id, userMsg.content)) {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          updated[updated.length - 1] = { ...last, content: last.content + chunk };
          return updated;
        });
      }
    } catch (err) {
      console.error('Chat error:', err);
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (!last.content) {
          updated[updated.length - 1] = { ...last, content: 'Failed to get response.' };
        }
        return updated;
      });
    } finally {
      setIsStreaming(false);
    }
  }, [input, assessment, isStreaming]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function parseCitations(content: string): (string | { type: 'citation'; label: string })[] {
    const parts: (string | { type: 'citation'; label: string })[] = [];
    const regex = /\[citation:(\d+)\]/g;
    let lastIndex = 0;
    let match;
    while ((match = regex.exec(content)) !== null) {
      if (match.index > lastIndex) {
        parts.push(content.slice(lastIndex, match.index));
      }
      parts.push({ type: 'citation', label: match[1] });
      lastIndex = regex.lastIndex;
    }
    if (lastIndex < content.length) {
      parts.push(content.slice(lastIndex));
    }
    return parts;
  }

  const disabled = !assessment;

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="chat-fab"
        title="Open chat"
        aria-label="Open chat"
      >
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="chat-fab-icon">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          <path d="M8 9h8" />
          <path d="M8 13h5" />
        </svg>
      </button>
    );
  }

  return (
    <div className="chat-window">
      {/* Header */}
      <div className="chat-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', background: 'var(--primary-light)', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--primary)' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '15px', color: 'var(--text-main)', letterSpacing: '-0.01em' }}>
              Regulatory Assistant
            </div>
            {assessment && (
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px', fontWeight: 600 }}>
                {assessment.parcel.address.split(',')[0]}
              </div>
            )}
          </div>
        </div>
        <button
          onClick={() => setIsOpen(false)}
          className="btn-secondary"
          style={{ padding: 0, borderRadius: '50%', width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '20px', border: 'none', background: 'rgba(0,0,0,0.05)' }}
          aria-label="Close chat"
        >
          &times;
        </button>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {disabled && (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '14px', marginTop: '60px' }}>
            <div style={{ fontSize: '24px', marginBottom: '12px' }}>👋</div>
            Please select a parcel to start chatting.
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`message ${msg.role === 'user' ? 'message-user' : 'message-assistant'}`}
          >
            {msg.role === 'assistant'
              ? parseCitations(msg.content).map((part, j) =>
                  typeof part === 'string' ? (
                    <span key={j}>{part}</span>
                  ) : (
                    <span
                      key={j}
                      style={{
                        display: 'inline-block',
                        padding: '0 6px',
                        margin: '0 2px',
                        borderRadius: '6px',
                        background: 'rgba(37, 99, 235, 0.1)',
                        color: 'var(--primary)',
                        fontSize: '11px',
                        fontWeight: 700,
                        cursor: 'help',
                      }}
                    >
                      [{part.label}]
                    </span>
                  ),
                )
              : msg.content}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="chat-input-area">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={disabled ? 'Select an address...' : 'Ask about local regulations...'}
          rows={1}
          className="chat-textarea"
        />
        <button
          onClick={sendMessage}
          disabled={disabled || isStreaming || !input.trim()}
          className="btn-primary"
          style={{ padding: '10px 16px', borderRadius: 'var(--radius-md)' }}
        >
          {isStreaming ? '...' : 'Send'}
        </button>
      </div>
    </div>
  );
}

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
        Math.min(textareaRef.current.scrollHeight, 96) + 'px';
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

  // FAB toggle button
  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          background: '#3b82f6',
          color: '#fff',
          border: 'none',
          cursor: 'pointer',
          fontSize: '20px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
          zIndex: 50,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
        title="Open chat"
        aria-label="Open chat"
      >
        {'\u{1F4AC}'}
      </button>
    );
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        width: '380px',
        height: '100vh',
        background: '#fff',
        borderLeft: '1px solid #e5e7eb',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 40,
        boxShadow: '-4px 0 12px rgba(0,0,0,0.08)',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid #e5e7eb',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#f9fafb',
        }}
      >
        <div>
          <div style={{ fontWeight: 600, fontSize: '14px', color: '#111827' }}>
            Follow-up Chat
          </div>
          {assessment && (
            <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '2px' }}>
              {assessment.parcel.address} &middot; {assessment.zoning.zone_class}
            </div>
          )}
        </div>
        <button
          onClick={() => setIsOpen(false)}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: '18px',
            color: '#6b7280',
            padding: '4px',
          }}
          aria-label="Close chat"
        >
          &times;
        </button>
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '12px 16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
        }}
      >
        {disabled && (
          <div style={{ textAlign: 'center', color: '#9ca3af', fontSize: '14px', marginTop: '40px' }}>
            Run an assessment first
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '85%',
            }}
          >
            <div
              data-testid={`message-${msg.role}`}
              style={{
                padding: '8px 12px',
                borderRadius: '12px',
                fontSize: '13px',
                lineHeight: 1.5,
                background: msg.role === 'user' ? '#3b82f6' : '#f3f4f6',
                color: msg.role === 'user' ? '#fff' : '#111827',
              }}
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
                          borderRadius: '8px',
                          background: '#dbeafe',
                          color: '#1d4ed8',
                          fontSize: '11px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        [{part.label}]
                      </span>
                    ),
                  )
                : msg.content}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div
        style={{
          padding: '12px 16px',
          borderTop: '1px solid #e5e7eb',
          display: 'flex',
          gap: '8px',
          alignItems: 'flex-end',
        }}
      >
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={disabled ? 'Run an assessment first' : 'Ask a follow-up question...'}
          rows={1}
          style={{
            flex: 1,
            resize: 'none',
            border: '1px solid #d1d5db',
            borderRadius: '8px',
            padding: '8px 12px',
            fontSize: '13px',
            lineHeight: 1.5,
            outline: 'none',
            fontFamily: 'inherit',
            minHeight: '36px',
            maxHeight: '96px',
          }}
        />
        <button
          onClick={sendMessage}
          disabled={disabled || isStreaming || !input.trim()}
          style={{
            background: '#3b82f6',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            padding: '8px 12px',
            cursor: disabled || isStreaming || !input.trim() ? 'not-allowed' : 'pointer',
            opacity: disabled || isStreaming || !input.trim() ? 0.5 : 1,
            fontSize: '13px',
            fontWeight: 600,
            whiteSpace: 'nowrap',
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}

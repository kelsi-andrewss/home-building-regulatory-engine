import { useState, useRef, useEffect } from 'react';
import { useAssessment } from '../context/AssessmentContext';
import { sendFeedback } from '../api/client';

interface Props {
  constraintName: string;
}

export default function FeedbackButton({ constraintName }: Props) {
  const { assessment, feedbackMap, dispatch } = useAssessment();
  const current = feedbackMap[constraintName] ?? null;
  const [showPopover, setShowPopover] = useState(false);
  const [reason, setReason] = useState('');
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setShowPopover(false);
      }
    }
    if (showPopover) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showPopover]);

  function handleVote(vote: 'up' | 'down') {
    const newVote = current === vote ? null : vote;
    dispatch({ type: 'SET_FEEDBACK', payload: { name: constraintName, vote: newVote } });

    if (assessment) {
      sendFeedback(assessment.assessment_id, constraintName, newVote).catch(() => {});
    }

    if (newVote === 'down') {
      setShowPopover(true);
    } else {
      setShowPopover(false);
    }
  }

  function submitReason() {
    if (assessment && reason.trim()) {
      sendFeedback(assessment.assessment_id, constraintName, 'down', reason.trim()).catch(() => {});
    }
    setShowPopover(false);
    setReason('');
  }

  const btnBase: React.CSSProperties = {
    width: '24px',
    height: '24px',
    border: 'none',
    background: 'none',
    cursor: 'pointer',
    borderRadius: '4px',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '14px',
    padding: 0,
    position: 'relative',
  };

  return (
    <div style={{ display: 'inline-flex', gap: '2px', position: 'relative' }}>
      <button
        onClick={() => handleVote('up')}
        style={{
          ...btnBase,
          color: current === 'up' ? '#22c55e' : '#9ca3af',
        }}
        title="Thumbs up"
        aria-label={`Thumbs up for ${constraintName}`}
        data-testid="feedback-up"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill={current === 'up' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
        </svg>
      </button>
      <button
        onClick={() => handleVote('down')}
        style={{
          ...btnBase,
          color: current === 'down' ? '#ef4444' : '#9ca3af',
        }}
        title="Thumbs down"
        aria-label={`Thumbs down for ${constraintName}`}
        data-testid="feedback-down"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill={current === 'down' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10zM17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
        </svg>
      </button>

      {showPopover && (
        <div
          ref={popoverRef}
          style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            background: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            padding: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 20,
            width: '200px',
          }}
        >
          <input
            type="text"
            placeholder="Why is this incorrect?"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') submitReason();
            }}
            style={{
              width: '100%',
              padding: '4px 8px',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              fontSize: '12px',
              outline: 'none',
              boxSizing: 'border-box',
            }}
          />
          <button
            onClick={submitReason}
            style={{
              marginTop: '4px',
              width: '100%',
              padding: '4px',
              background: '#3b82f6',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Submit
          </button>
        </div>
      )}
    </div>
  );
}

import { useState, useEffect, useRef } from 'react';
import type { GeocodingResult } from '../api/client';
import { geocodeAddress } from '../api/client';

interface Props {
  onSelect: (candidate: GeocodingResult) => void;
}

export default function AddressSearch({ onSelect }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<GeocodingResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (query.length < 3) {
      setResults([]);
      setIsOpen(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsLoading(true);
      try {
        const data = await geocodeAddress(query);
        setResults(data);
        setIsOpen(data.length > 0);
      } catch {
        setResults([]);
        setIsOpen(false);
      } finally {
        setIsLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  function handleSelect(candidate: GeocodingResult) {
    setQuery(candidate.address);
    setIsOpen(false);
    onSelect(candidate);
  }

  return (
    <div ref={containerRef} className="search-container">
      <div className="search-input-wrapper">
        <div style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', pointerEvents: 'none' }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
        </div>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search LA property addresses..."
          className="input-field"
          style={{ paddingLeft: '36px' }}
          onFocus={() => {
            if (results.length > 0) setIsOpen(true);
          }}
        />
        {isLoading && <div className="search-spinner" style={{ right: '16px' }} />}
      </div>

      {isOpen && results.length > 0 && (
        <ul className="suggestions-list">
          {results.map((r) => (
            <li
              key={r.apn}
              onClick={() => handleSelect(r)}
              className="suggestion-item"
            >
              <div className="suggestion-address">{r.address}</div>
              <div className="suggestion-apn">APN: {r.apn}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}


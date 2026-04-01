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
    <div ref={containerRef} style={{ position: 'relative' }}>
      <div style={{ position: 'relative' }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter an LA address..."
          style={{
            width: '100%',
            padding: '10px 36px 10px 12px',
            border: '1px solid #d1d5db',
            borderRadius: '6px',
            fontSize: '14px',
            boxSizing: 'border-box',
            outline: 'none',
          }}
          onFocus={() => {
            if (results.length > 0) setIsOpen(true);
          }}
        />
        {isLoading && (
          <span
            style={{
              position: 'absolute',
              right: '10px',
              top: '50%',
              transform: 'translateY(-50%)',
              width: '16px',
              height: '16px',
              border: '2px solid #d1d5db',
              borderTopColor: '#3b82f6',
              borderRadius: '50%',
              animation: 'spin 0.6s linear infinite',
            }}
          />
        )}
      </div>

      {isOpen && results.length > 0 && (
        <ul
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            zIndex: 10,
            background: '#fff',
            border: '1px solid #d1d5db',
            borderRadius: '0 0 6px 6px',
            margin: 0,
            padding: 0,
            listStyle: 'none',
            maxHeight: '240px',
            overflowY: 'auto',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          }}
        >
          {results.map((r) => (
            <li
              key={r.apn}
              onClick={() => handleSelect(r)}
              style={{
                padding: '10px 12px',
                cursor: 'pointer',
                borderBottom: '1px solid #f3f4f6',
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.background = '#f3f4f6';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.background = '#fff';
              }}
            >
              <div style={{ fontSize: '14px', fontWeight: 500 }}>{r.address}</div>
              <div style={{ fontSize: '12px', color: '#6b7280' }}>APN: {r.apn}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

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
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter an LA address..."
          className="input-field"
          onFocus={() => {
            if (results.length > 0) setIsOpen(true);
          }}
        />
        {isLoading && <div className="search-spinner" />}
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

import { useState } from 'react';
import type { AssessmentResponse, BuildingType, Confidence, DesignConstraintResponse } from '../api/client';
import DesignConstraintsPanel from './DesignConstraintsPanel';
import FeedbackButton from './FeedbackButton';
import ParameterInputs from './ParameterInputs';

const CONFIDENCE_COLORS: Record<Confidence, string> = {
  verified: '#10b981',
  interpreted: '#f59e0b',
  unknown: '#ef4444',
};

const TYPE_LABELS: Record<BuildingType, string> = {
  SFH: 'Single Family Home',
  ADU: 'Accessory Dwelling Unit',
  GH: 'Guest House',
  DUP: 'Duplex',
};

interface Props {
  assessment: AssessmentResponse | null;
  selectedType: BuildingType;
  designConstraints?: DesignConstraintResponse | null;
  onHoverConstraint: (name: string | null) => void;
}

export default function BuildabilityReport({ assessment, selectedType, designConstraints, onHoverConstraint }: Props) {
  const [expandedCitations, setExpandedCitations] = useState<Set<string>>(new Set());

  if (!assessment) {
    return (
      <div style={{ padding: '24px 0', color: '#6b7280', fontSize: '14px', textAlign: 'center' }}>
        Search for an address to see buildability constraints.
      </div>
    );
  }

  const buildingType = assessment.building_types.find((bt) => bt.type === selectedType);

  if (!buildingType) {
    return (
      <div style={{ padding: '24px 0', color: '#6b7280', fontSize: '14px', textAlign: 'center' }}>
        No data available for this building type.
      </div>
    );
  }

  function toggleCitation(name: string) {
    setExpandedCitations((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  return (
    <div>
      <ParameterInputs />
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          marginBottom: '12px',
          paddingBottom: '8px',
          borderBottom: '1px solid #e5e7eb',
        }}
      >
        <span style={{ fontWeight: 600, fontSize: '15px' }}>{TYPE_LABELS[selectedType]}</span>
        <span
          style={{
            padding: '2px 8px',
            borderRadius: '12px',
            fontSize: '12px',
            fontWeight: 600,
            background: buildingType.allowed ? '#d1fae5' : '#fce7f3',
            color: buildingType.allowed ? '#065f46' : '#9f1239',
          }}
        >
          {buildingType.allowed ? 'Allowed' : 'Not Allowed'}
        </span>
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
            <th style={{ padding: '6px 8px', fontWeight: 600, color: '#374151' }}>Constraint</th>
            <th style={{ padding: '6px 8px', fontWeight: 600, color: '#374151' }}>Value</th>
            <th style={{ padding: '6px 8px', fontWeight: 600, color: '#374151' }}>Confidence</th>
            <th style={{ padding: '6px 4px', fontWeight: 600, color: '#374151', width: '40px' }}></th>
            <th style={{ padding: '6px 4px', fontWeight: 600, color: '#374151', width: '56px' }}></th>
          </tr>
        </thead>
        <tbody>
          {buildingType.constraints.map((c) => (
            <tr
              key={c.name}
              onMouseEnter={() => onHoverConstraint(c.name)}
              onMouseLeave={() => onHoverConstraint(null)}
            >
              <td colSpan={5} style={{ padding: 0 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <tbody>
                    <tr style={{ borderBottom: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '8px', color: '#374151' }}>{c.name}</td>
                      <td style={{ padding: '8px', color: '#374151' }}>{c.value}</td>
                      <td style={{ padding: '8px' }}>
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '2px 8px',
                            borderRadius: '10px',
                            fontSize: '11px',
                            fontWeight: 600,
                            color: '#fff',
                            background: CONFIDENCE_COLORS[c.confidence],
                          }}
                        >
                          {c.confidence}
                        </span>
                      </td>
                      <td style={{ padding: '8px 4px', width: '40px', textAlign: 'center' }}>
                        {c.citation && (
                          <button
                            onClick={() => toggleCitation(c.name)}
                            style={{
                              background: 'none',
                              border: 'none',
                              cursor: 'pointer',
                              fontSize: '12px',
                              color: '#3b82f6',
                              fontWeight: 600,
                              padding: '2px 4px',
                            }}
                            title="Show citation"
                          >
                            {expandedCitations.has(c.name) ? '\u25B2' : 'cite'}
                          </button>
                        )}
                      </td>
                      <td style={{ padding: '4px', width: '56px', textAlign: 'center' }}>
                        <FeedbackButton constraintName={c.name} />
                      </td>
                    </tr>
                    {expandedCitations.has(c.name) && (
                      <tr>
                        <td
                          colSpan={5}
                          style={{
                            padding: '8px 12px 12px',
                            background: '#f9fafb',
                            fontSize: '12px',
                            color: '#4b5563',
                            lineHeight: 1.5,
                          }}
                        >
                          <div style={{ marginBottom: '4px' }}>
                            <strong>Citation:</strong> {c.citation}
                          </div>
                          <div>
                            <strong>Explanation:</strong> {c.explanation}
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {designConstraints && <DesignConstraintsPanel data={designConstraints} />}
    </div>
  );
}

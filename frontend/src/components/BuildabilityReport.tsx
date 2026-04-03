import { useState } from 'react';
import type { AssessmentResponse, BuildingType, DesignConstraintResponse } from '../api/client';
import DesignConstraintsPanel from './DesignConstraintsPanel';
import FeedbackButton from './FeedbackButton';
import ParameterInputs from './ParameterInputs';

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
      <div style={{ padding: '24px 0', color: 'var(--text-muted)', fontSize: '14px', textAlign: 'center' }}>
        Search for an address to see buildability constraints.
      </div>
    );
  }

  const buildingType = assessment.building_types.find((bt) => bt.type === selectedType);

  if (!buildingType) {
    return (
      <div style={{ padding: '24px 0', color: 'var(--text-muted)', fontSize: '14px', textAlign: 'center' }}>
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
      <div className="section-header">
        <span className="section-title">{TYPE_LABELS[selectedType]}</span>
        <span className={`badge ${buildingType.allowed ? 'badge-success' : 'badge-error'}`}>
          {buildingType.allowed ? 'Allowed' : 'Not Allowed'}
        </span>
      </div>

      <table className="data-table">
        <thead>
          <tr>
            <th>Constraint</th>
            <th>Value</th>
            <th>Confidence</th>
            <th style={{ width: '40px' }}></th>
            <th style={{ width: '56px' }}></th>
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
                    <tr>
                      <td style={{ padding: '12px 8px', color: 'var(--text-main)', width: '30%' }}>{c.name}</td>
                      <td style={{ padding: '12px 8px', color: 'var(--text-main)', width: '25%' }}>{c.value}</td>
                      <td style={{ padding: '12px 8px' }}>
                        <span className={`badge badge-confidence-${c.confidence}`}>
                          {c.confidence}
                        </span>
                      </td>
                      <td style={{ padding: '12px 4px', width: '40px', textAlign: 'center' }}>
                        {c.citation && (
                          <button
                            onClick={() => toggleCitation(c.name)}
                            className="btn-secondary"
                            style={{ padding: '2px 6px', fontSize: '11px' }}
                            title="Show citation"
                          >
                            {expandedCitations.has(c.name) ? '\u25B4' : 'cite'}
                          </button>
                        )}
                      </td>
                      <td style={{ padding: '12px 4px', width: '56px', textAlign: 'center' }}>
                        <FeedbackButton constraintName={c.name} />
                      </td>
                    </tr>
                    {expandedCitations.has(c.name) && (
                      <tr>
                        <td colSpan={5}>
                          <div className="expansion-content">
                            <div style={{ marginBottom: '4px' }}>
                              <strong>Citation:</strong> {c.citation}
                            </div>
                            <div>
                              <strong>Explanation:</strong> {c.explanation}
                            </div>
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

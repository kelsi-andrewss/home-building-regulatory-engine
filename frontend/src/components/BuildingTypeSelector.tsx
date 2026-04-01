import type { BuildingType } from '../api/client';

const LABELS: Record<BuildingType, string> = {
  SFH: 'Single Family',
  ADU: 'ADU',
  GH: 'Guest House',
  DUP: 'Duplex',
};

const ALL_TYPES: BuildingType[] = ['SFH', 'ADU', 'GH', 'DUP'];

interface Props {
  selectedType: BuildingType;
  availableTypes: BuildingType[];
  onSelect: (type: BuildingType) => void;
}

export default function BuildingTypeSelector({ selectedType, availableTypes, onSelect }: Props) {
  return (
    <div style={{ display: 'flex', gap: '4px', marginBottom: '16px' }}>
      {ALL_TYPES.map((t) => {
        const isActive = t === selectedType;
        const isDisabled = !availableTypes.includes(t);

        return (
          <button
            key={t}
            onClick={() => onSelect(t)}
            disabled={isDisabled}
            style={{
              flex: 1,
              padding: '8px 4px',
              fontSize: '13px',
              fontWeight: 500,
              border: '1px solid',
              borderColor: isActive ? '#3b82f6' : '#d1d5db',
              borderRadius: '6px',
              cursor: isDisabled ? 'not-allowed' : 'pointer',
              background: isActive ? '#3b82f6' : isDisabled ? '#f3f4f6' : '#fff',
              color: isActive ? '#fff' : isDisabled ? '#9ca3af' : '#374151',
              transition: 'all 0.15s',
            }}
          >
            {LABELS[t]}
          </button>
        );
      })}
    </div>
  );
}

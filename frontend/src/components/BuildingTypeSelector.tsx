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
    <div className="type-selector">
      {ALL_TYPES.map((t) => {
        const isActive = t === selectedType;
        const isDisabled = !availableTypes.includes(t);

        return (
          <button
            key={t}
            onClick={() => onSelect(t)}
            disabled={isDisabled}
            className={`type-btn ${isActive ? 'active' : ''}`}
          >
            {LABELS[t]}
          </button>
        );
      })}
    </div>
  );
}

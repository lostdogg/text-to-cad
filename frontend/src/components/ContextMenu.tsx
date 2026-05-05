import React, { useEffect, useRef } from 'react';
import useCADStore from '../store/cadStore';
import { BooleanOpType, ManufacturingType } from '../types/cad';

export interface ContextMenuProps {
  x: number;
  y: number;
  onClose: () => void;
  modelId?: string;
  onRequestBoolean?: (op: BooleanOpType) => void;
}

interface MenuItem {
  label: string;
  shortcut?: string;
  action: () => void;
  divider?: false;
  icon?: string;
}

interface Divider {
  divider: true;
}

type MenuEntry = MenuItem | Divider;

export const ContextMenu: React.FC<ContextMenuProps> = ({
  x, y, onClose, modelId, onRequestBoolean,
}) => {
  const menuRef = useRef<HTMLDivElement>(null);
  const { exportModel, exportGCode, downloadReport, setManufacturingTab } = useCADStore();

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener('keydown', handleKey);
    document.addEventListener('mousedown', handleClick);
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.removeEventListener('mousedown', handleClick);
    };
  }, [onClose]);

  // Adjust position so menu stays on screen
  const menuStyle: React.CSSProperties = {
    left: Math.min(x, window.innerWidth - 200),
    top: Math.min(y, window.innerHeight - 300),
  };

  const entries: MenuEntry[] = [
    { label: 'Export STL',  shortcut: 'E S', icon: '📦', action: () => modelId && exportModel('stl', modelId) },
    { label: 'Export OBJ',  shortcut: 'E O', icon: '📦', action: () => modelId && exportModel('obj', modelId) },
    { label: 'Export STEP', shortcut: 'E P', icon: '📦', action: () => modelId && exportModel('step', modelId) },
    { divider: true },
    { label: 'G-code (CNC)',     icon: '⚙️', action: () => modelId && exportGCode('cnc', modelId) },
    { label: 'G-code (3D Print)',icon: '🖨️', action: () => modelId && exportGCode('3dprint', modelId) },
    { label: 'G-code (Laser)',   icon: '🔴', action: () => modelId && exportGCode('laser', modelId) },
    { divider: true },
    {
      label: 'Boolean Union',        shortcut: 'B U', icon: '∪',
      action: () => onRequestBoolean?.(BooleanOpType.UNION),
    },
    {
      label: 'Boolean Intersection', shortcut: 'B I', icon: '∩',
      action: () => onRequestBoolean?.(BooleanOpType.INTERSECTION),
    },
    {
      label: 'Boolean Subtract',     shortcut: 'B S', icon: '−',
      action: () => onRequestBoolean?.(BooleanOpType.SUBTRACTION),
    },
    { divider: true },
    {
      label: 'CNC Settings',  icon: '⚙️',
      action: () => { setManufacturingTab(ManufacturingType.CNC_3AXIS); onClose(); },
    },
    {
      label: 'Print Settings', icon: '🖨️',
      action: () => { setManufacturingTab(ManufacturingType.PRINTING_3D); onClose(); },
    },
    {
      label: 'Laser Settings', icon: '🔴',
      action: () => { setManufacturingTab(ManufacturingType.LASER_CUTTING); onClose(); },
    },
    { divider: true },
    { label: 'Download QC Report', icon: '📋', action: () => modelId && downloadReport(modelId) },
  ];

  return (
    <div
      ref={menuRef}
      className="fixed z-50 bg-zinc-800 border border-zinc-600 rounded-lg shadow-2xl py-1 w-52 text-sm"
      style={menuStyle}
    >
      {entries.map((entry, i) => {
        if ('divider' in entry && entry.divider) {
          return <div key={i} className="border-t border-zinc-700 my-1" />;
        }
        const item = entry as MenuItem;
        return (
          <button
            key={i}
            onClick={() => { item.action(); onClose(); }}
            className="flex items-center justify-between w-full px-3 py-1.5 text-zinc-300 hover:bg-zinc-700 hover:text-white transition-colors"
          >
            <span className="flex items-center gap-2">
              {item.icon && <span className="w-4 text-center">{item.icon}</span>}
              {item.label}
            </span>
            {item.shortcut && (
              <kbd className="text-xs text-zinc-500 font-mono">{item.shortcut}</kbd>
            )}
          </button>
        );
      })}
    </div>
  );
};

export default ContextMenu;

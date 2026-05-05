import React, { useState, useRef } from 'react';
import useCADStore from '../store/cadStore';
import { ManufacturingType } from '../types/cad';

const EXAMPLE_PROMPTS = [
  'Create a 50mm × 30mm × 10mm aluminum mounting bracket with four 5mm holes in the corners',
  'Make a cylinder with 20mm diameter and 40mm height, subtract a 10mm hole down the center',
  'Design a sphere with 25mm radius',
  'Create a 100mm × 50mm × 3mm acrylic panel for laser cutting',
  'Build a torus with 30mm major radius and 5mm minor radius',
  'Subtract a 5mm cylinder from the center of a 20mm cube',
];

const COORDINATE_DIAGRAM = `
   Z+ (Up)
   │
   │   Y+ (Back)
   │  ╱
   │ ╱
   └────── X+ (Right)
`;

export const SemanticWorkspace: React.FC = () => {
  const [inputText, setInputText] = useState('');
  const [mfgType, setMfgType] = useState<ManufacturingType | ''>('');
  const [showHistory, setShowHistory] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { generateFromText, isLoading, error, clearError, models, lastResponse } = useCADStore();

  const handleGenerate = async () => {
    if (!inputText.trim() || isLoading) return;
    await generateFromText(inputText.trim(), mfgType as ManufacturingType | undefined);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleGenerate();
  };

  const applyExample = (text: string) => {
    setInputText(text);
    textareaRef.current?.focus();
  };

  return (
    <div className="panel flex flex-col gap-4 p-4 h-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-sky-400">Semantic Workspace</h2>
        <button
          onClick={() => setShowHistory((v) => !v)}
          className="text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          {showHistory ? 'Hide' : 'Show'} History
        </button>
      </div>

      {/* Coordinate system diagram */}
      <div className="bg-zinc-800 rounded p-3 flex items-start gap-4">
        <pre className="text-xs text-zinc-400 font-mono leading-tight select-none">
          {COORDINATE_DIAGRAM}
        </pre>
        <div className="text-xs text-zinc-400 space-y-1">
          <p><span className="text-red-400 font-bold">X+</span> Right</p>
          <p><span className="text-green-400 font-bold">Y+</span> Back</p>
          <p><span className="text-blue-400 font-bold">Z+</span> Up</p>
          <p className="text-zinc-500 mt-2">All dims in mm</p>
        </div>
      </div>

      {/* Input area */}
      <div className="flex flex-col gap-2 flex-1">
        <label className="label">Describe your part</label>
        <textarea
          ref={textareaRef}
          className="textarea flex-1 min-h-[120px]"
          placeholder="e.g. Create a 50mm × 30mm × 10mm box with a 5mm hole through the center..."
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
        />
        <p className="text-xs text-zinc-500">Tip: Press Ctrl+Enter to generate</p>
      </div>

      {/* Manufacturing type */}
      <div>
        <label className="label">Manufacturing Process (optional)</label>
        <select
          className="input"
          value={mfgType}
          onChange={(e) => setMfgType(e.target.value as ManufacturingType | '')}
        >
          <option value="">— None selected —</option>
          <option value={ManufacturingType.CNC_3AXIS}>3-Axis CNC Machining</option>
          <option value={ManufacturingType.PRINTING_3D}>3D Printing (FDM/SLA/SLS)</option>
          <option value={ManufacturingType.LASER_CUTTING}>Laser Cutting</option>
        </select>
      </div>

      {/* Example prompts */}
      <div>
        <label className="label">Example Prompts</label>
        <div className="flex flex-col gap-1.5 max-h-32 overflow-y-auto">
          {EXAMPLE_PROMPTS.map((p, i) => (
            <button
              key={i}
              onClick={() => applyExample(p)}
              className="text-left text-xs text-zinc-400 hover:text-sky-300 bg-zinc-800 hover:bg-zinc-700 px-2 py-1.5 rounded transition-colors truncate"
              title={p}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Generate button */}
      <button
        onClick={handleGenerate}
        disabled={isLoading || !inputText.trim()}
        className="btn-primary justify-center py-3 text-base font-semibold"
      >
        {isLoading ? (
          <>
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Generating...
          </>
        ) : (
          <>
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Generate CAD Model
          </>
        )}
      </button>

      {/* Error display */}
      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded p-3 flex items-start gap-2">
          <svg className="h-4 w-4 text-red-400 mt-0.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          <div className="flex-1">
            <p className="text-sm text-red-300">{error}</p>
            <button onClick={clearError} className="text-xs text-red-400 hover:text-red-300 mt-1">
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Last response info */}
      {lastResponse && !isLoading && (
        <div className="bg-green-900/20 border border-green-800 rounded p-2 text-xs text-green-400">
          ✓ Generated in {lastResponse.processing_time.toFixed(2)}s ·{' '}
          {lastResponse.mesh_data?.vertex_count.toLocaleString()} vertices ·{' '}
          {lastResponse.mesh_data?.face_count.toLocaleString()} faces
        </div>
      )}

      {/* History */}
      {showHistory && models.length > 0 && (
        <div className="border-t border-zinc-700 pt-3">
          <label className="label">Recent Models</label>
          <div className="flex flex-col gap-1 max-h-40 overflow-y-auto">
            {models.slice(0, 10).map((m) => (
              <div
                key={m.id}
                className="text-xs text-zinc-400 bg-zinc-800 px-2 py-1.5 rounded truncate cursor-pointer hover:text-zinc-200 hover:bg-zinc-700 transition-colors"
                title={m.source_text}
                onClick={() => setInputText(m.source_text ?? '')}
              >
                {m.name}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default SemanticWorkspace;

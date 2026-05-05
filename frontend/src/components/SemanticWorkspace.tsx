import React, { useState, useRef, useEffect, useCallback } from 'react';
import useCADStore from '../store/cadStore';
import { ManufacturingType } from '../types/cad';

// ------------------------------------------------------------------ //
// Example prompts grouped by category                                 //
// ------------------------------------------------------------------ //

const EXAMPLE_CATEGORIES = [
  {
    label: 'Basic Shapes',
    prompts: [
      'Create a 50mm × 30mm × 10mm box',
      'Make a sphere with 25mm radius',
      'Design a cylinder with 20mm diameter and 40mm height',
      'Build a torus with 30mm major radius and 5mm minor radius',
      'Make a cone with 15mm radius and 30mm height',
    ],
  },
  {
    label: 'Boolean Operations',
    prompts: [
      'Subtract a 5mm cylinder from the center of a 20mm cube',
      'Make a cylinder with 20mm diameter and 40mm height, subtract a 10mm hole down the center',
      'Union a 30mm box and a 20mm sphere',
    ],
  },
  {
    label: 'Manufacturing Ready',
    prompts: [
      'Create a 50mm × 30mm × 10mm aluminum mounting bracket with four 5mm holes in the corners',
      'Create a 100mm × 50mm × 3mm acrylic panel for laser cutting',
      'Design a 40mm × 40mm × 8mm steel bracket for CNC machining',
    ],
  },
];

// ------------------------------------------------------------------ //
// Loading stage animation                                             //
// ------------------------------------------------------------------ //

const LOADING_STAGES = [
  { label: 'NLP Agent: Parsing text…', icon: '🧠' },
  { label: 'CSG Agent: Building mesh…', icon: '🔧' },
  { label: 'Validation: Checking geometry…', icon: '✅' },
];

function LoadingStages() {
  const [stage, setStage] = useState(0);

  useEffect(() => {
    const timers = [
      setTimeout(() => setStage(1), 700),
      setTimeout(() => setStage(2), 1600),
    ];
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="flex flex-col gap-2">
      {LOADING_STAGES.map((s, i) => (
        <div
          key={i}
          className={`flex items-center gap-2 text-xs transition-opacity duration-300 ${
            i <= stage ? 'opacity-100' : 'opacity-25'
          }`}
        >
          <span className="w-4 text-center">{s.icon}</span>
          <span
            className={
              i < stage
                ? 'text-green-400 line-through'
                : i === stage
                ? 'text-sky-300 font-medium'
                : 'text-zinc-500'
            }
          >
            {s.label}
          </span>
          {i === stage && (
            <svg className="animate-spin h-3 w-3 text-sky-400 ml-auto shrink-0" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          )}
          {i < stage && (
            <span className="text-green-500 ml-auto text-xs">✓</span>
          )}
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ //
// Main component                                                      //
// ------------------------------------------------------------------ //

export const SemanticWorkspace: React.FC = () => {
  const [inputText, setInputText] = useState('');
  const [mfgType, setMfgType] = useState<ManufacturingType | ''>('');
  const [showHistory, setShowHistory] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [openCategory, setOpenCategory] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { generateFromText, isLoading, error, clearError, models, agentLogs } =
    useCADStore();

  // Auto-resize textarea
  const resizeTextarea = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 240)}px`;
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputText(e.target.value);
    resizeTextarea();
  };

  // Reset height when text is cleared
  useEffect(() => {
    if (!inputText) resizeTextarea();
  }, [inputText, resizeTextarea]);

  const handleGenerate = async () => {
    if (!inputText.trim() || isLoading) return;
    await generateFromText(inputText.trim(), mfgType as ManufacturingType | undefined);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleGenerate();
  };

  const applyExample = (text: string) => {
    setInputText(text);
    setTimeout(resizeTextarea, 0);
    textareaRef.current?.focus();
    setOpenCategory(null);
  };

  const charCount = inputText.length;

  return (
    <div className="panel flex flex-col gap-0 h-full overflow-y-auto">
      {/* SW PropertyManager-style section header */}
      <div className="cad-section-header">
        <svg className="w-3 h-3 text-sky-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
        </svg>
        Feature Manager
        <button
          onClick={() => setShowHistory((v) => !v)}
          className="ml-auto text-zinc-500 hover:text-zinc-300 transition-colors normal-case text-[10px] tracking-normal font-normal"
        >
          {showHistory ? 'Hide' : 'History'}
        </button>
      </div>

      <div className="flex flex-col gap-4 p-4">

      {/* Input area */}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <label className="label !mb-0">Describe your part</label>
          <span className={`text-xs ${charCount > 400 ? 'text-amber-400' : 'text-zinc-600'}`}>
            {charCount}
          </span>
        </div>
        <textarea
          ref={textareaRef}
          className="textarea min-h-[96px] overflow-hidden"
          style={{ resize: 'none' }}
          placeholder="e.g. Create a 50mm × 30mm × 10mm box with a 5mm hole through the center…"
          value={inputText}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
        />
        <p className="text-xs text-zinc-600">
          Tip: <kbd className="bg-zinc-800 border border-zinc-700 rounded px-1 py-0.5 font-mono text-zinc-400">Ctrl</kbd>
          {' + '}
          <kbd className="bg-zinc-800 border border-zinc-700 rounded px-1 py-0.5 font-mono text-zinc-400">↵</kbd>
          {' to generate'}
        </p>
      </div>

      {/* Manufacturing type */}
      <div>
        <label className="label">Manufacturing Process <span className="text-zinc-600 font-normal">(optional)</span></label>
        <select
          className="input"
          value={mfgType}
          onChange={(e) => setMfgType(e.target.value as ManufacturingType | '')}
        >
          <option value="">— None selected —</option>
          <option value={ManufacturingType.CNC_3AXIS}>⚙️ 3-Axis CNC Machining</option>
          <option value={ManufacturingType.PRINTING_3D}>🖨 3D Printing (FDM/SLA/SLS)</option>
          <option value={ManufacturingType.LASER_CUTTING}>🔴 Laser Cutting</option>
        </select>
      </div>

      {/* Generate button — Mastercam-style orange primary CTA */}
      <button
        onClick={handleGenerate}
        disabled={isLoading || !inputText.trim()}
        className="btn-mc justify-center py-2 text-sm font-semibold"
      >
        {isLoading ? (
          <>
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Generating…
          </>
        ) : (
          <>
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Generate CAD Model
          </>
        )}
      </button>

      {/* Multi-stage loading progress */}
      {isLoading && (
        <div className="bg-zinc-800/60 border border-zinc-600 rounded-sm px-3 py-2.5">
          <LoadingStages />
        </div>
      )}

      {/* Error display */}
      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded-sm p-3 flex items-start gap-2">
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

      {/* Agent logs (collapsible) */}
      {agentLogs.length > 0 && !isLoading && (
        <div className="border border-zinc-600 rounded-sm overflow-hidden">
          <button
            onClick={() => setShowLogs((v) => !v)}
            className="w-full flex items-center justify-between px-3 py-1.5 bg-zinc-800 text-xs text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700 transition-colors"
          >
            <span className="flex items-center gap-1.5">
              <span>⚙</span>
              <span>Agent Pipeline Logs ({agentLogs.length})</span>
            </span>
            <span className="text-zinc-500">{showLogs ? '▲' : '▼'}</span>
          </button>
          {showLogs && (
            <div className="bg-zinc-950 px-3 py-2 max-h-40 overflow-y-auto">
              {agentLogs.map((log, i) => (
                <p key={i} className="text-xs font-mono text-zinc-500 leading-5">{log}</p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Example prompts — categorized accordion */}
      <div>
        <label className="label">Example Prompts</label>
        <div className="flex flex-col gap-1">
          {EXAMPLE_CATEGORIES.map((cat) => (
            <div key={cat.label} className="border border-zinc-600 rounded-sm overflow-hidden">
              <button
                onClick={() => setOpenCategory(openCategory === cat.label ? null : cat.label)}
                className="w-full flex items-center justify-between px-3 py-1.5 bg-zinc-800 text-xs font-semibold text-zinc-300 hover:text-white hover:bg-zinc-700 transition-colors"
              >
                <span>{cat.label}</span>
                <span className="text-zinc-500">{openCategory === cat.label ? '▲' : '▼'}</span>
              </button>
              {openCategory === cat.label && (
                <div className="bg-zinc-900 divide-y divide-zinc-800">
                  {cat.prompts.map((p, i) => (
                    <button
                      key={i}
                      onClick={() => applyExample(p)}
                      className="block w-full text-left px-3 py-1.5 text-xs text-zinc-400 hover:text-sky-400 hover:bg-zinc-800 transition-colors"
                      title={p}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* History */}
      {showHistory && models.length > 0 && (
        <div className="border-t border-zinc-600 pt-3">
          <label className="label">Recent Models</label>
          <div className="flex flex-col gap-1 max-h-40 overflow-y-auto">
            {models.slice(0, 10).map((m) => (
              <div
                key={m.id}
                className="text-xs text-zinc-400 bg-zinc-800 px-2 py-1.5 rounded-sm truncate cursor-pointer hover:text-zinc-200 hover:bg-zinc-700 transition-colors"
                title={m.source_text}
                onClick={() => {
                  setInputText(m.source_text ?? '');
                  setTimeout(resizeTextarea, 0);
                }}
              >
                {m.name}
              </div>
            ))}
          </div>
        </div>
      )}
      </div>
    </div>
  );
};

export default SemanticWorkspace;


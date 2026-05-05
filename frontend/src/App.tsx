import React, { useState } from 'react';
import SemanticWorkspace from './components/SemanticWorkspace';
import CADViewer from './components/CADViewer';
import ManufacturingPanel from './components/ManufacturingPanel';
import CollaborationPanel from './components/CollaborationPanel';
import AIProviderPanel from './components/AIProviderPanel';
import ToastContainer from './components/Toast';
import useCADStore from './store/cadStore';

type PanelKey = 'workspace' | 'ai' | 'manufacturing' | 'collaboration';

const PANEL_LABELS: Record<PanelKey, { short: string; icon: string }> = {
  workspace:     { short: 'Feature Mgr',  icon: '◧' },
  ai:            { short: 'AI Config',    icon: '⬡' },
  manufacturing: { short: 'CAM / Mfg',   icon: '⚙' },
  collaboration: { short: 'Teams',        icon: '⬡' },
};

const MENU_ITEMS = ['File', 'Edit', 'View', 'Insert', 'Tools', 'Window', 'Help'];

const App: React.FC = () => {
  const [activePanel, setActivePanel] = useState<PanelKey>('workspace');
  const { toasts, removeToast, currentModel, models } = useCADStore();

  return (
    <div className="flex flex-col h-screen bg-zinc-900 text-zinc-100 overflow-hidden"
         style={{ fontFamily: '"Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif' }}>

      {/* ── Title Bar ────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-3 py-1.5 bg-zinc-950 border-b border-zinc-600 shrink-0 select-none">
        <div className="flex items-center gap-2.5">
          {/* 3D cube icon */}
          <svg className="w-5 h-5 text-sky-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
          </svg>
          <span className="font-semibold text-sm text-white tracking-wide">Text-to-CAD</span>
          <span className="hidden sm:inline text-zinc-500 text-xs border-l border-zinc-600 pl-2.5">
            AI‑Powered 3D CAD Generation
          </span>
        </div>

        <div className="flex items-center gap-4 text-xs">
          {currentModel && (
            <span className="text-zinc-400 hidden md:inline">
              Active:{' '}
              <span className="text-sky-400 font-medium">{currentModel.name}</span>
            </span>
          )}
          {models.length > 0 && (
            <span className="text-zinc-500 hidden md:inline">
              {models.length} model{models.length !== 1 ? 's' : ''}
            </span>
          )}
          <span className="flex items-center gap-1.5 text-zinc-400">
            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full inline-block animate-pulse" />
            API Ready
          </span>
        </div>
      </header>

      {/* ── Menu Bar ─────────────────────────────────────────────── */}
      <nav className="flex items-center px-1 bg-zinc-900 border-b border-zinc-600 shrink-0 select-none">
        {MENU_ITEMS.map((item) => (
          <button
            key={item}
            className="px-3 py-1 text-xs text-zinc-300 hover:bg-zinc-700 hover:text-white transition-colors rounded-sm"
          >
            {item}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2 pr-2 text-xs text-zinc-500">
          <span className="hidden lg:inline">Units: mm</span>
          <span className="text-zinc-600">|</span>
          <span className="hidden lg:inline text-zinc-500">Grid: 10 mm</span>
        </div>
      </nav>

      {/* ── Main Layout ──────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">

        {/* Left sidebar — SW PropertyManager */}
        <aside className="w-80 shrink-0 flex flex-col border-r border-zinc-600 overflow-hidden bg-zinc-800">

          {/* PropertyManager tab strip */}
          <div className="flex border-b border-zinc-600 bg-zinc-950 select-none">
            {(Object.keys(PANEL_LABELS) as PanelKey[]).map((key) => {
              const { short } = PANEL_LABELS[key];
              const isActive = activePanel === key;
              return (
                <button
                  key={key}
                  onClick={() => setActivePanel(key)}
                  title={short}
                  className={`flex-1 py-1.5 px-1 text-[10px] font-semibold tracking-wide transition-colors border-b-2 ${
                    isActive
                      ? 'border-b-sky-500 bg-zinc-800 text-sky-400'
                      : 'border-b-transparent text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/60'
                  }`}
                >
                  {short}
                </button>
              );
            })}
          </div>

          {/* Active panel content */}
          <div className="flex-1 overflow-y-auto">
            {activePanel === 'workspace'     && <SemanticWorkspace />}
            {activePanel === 'ai'            && <AIProviderPanel />}
            {activePanel === 'manufacturing' && <ManufacturingPanel />}
            {activePanel === 'collaboration' && <CollaborationPanel />}
          </div>
        </aside>

        {/* 3D Viewport */}
        <main className="flex-1 overflow-hidden bg-zinc-950">
          <CADViewer />
        </main>
      </div>

      {/* ── Status Bar ───────────────────────────────────────────── */}
      <footer className="px-3 py-1 bg-zinc-950 border-t border-zinc-600 shrink-0 flex items-center justify-between text-xs text-zinc-500 select-none">
        <div className="flex items-center gap-4">
          <span>
            <span className="text-red-400 font-bold">X+</span> Right
            {' · '}
            <span className="text-green-400 font-bold">Y+</span> Back
            {' · '}
            <span className="text-sky-400 font-bold">Z+</span> Up
          </span>
          <span className="text-zinc-600">|</span>
          <span>All dimensions in mm</span>
        </div>
        <span className="text-zinc-600">Text-to-CAD v1.0.0 · FastAPI + React Three Fiber</span>
      </footer>

      {/* Toast notifications */}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </div>
  );
};

export default App;


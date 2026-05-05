import React, { useState } from 'react';
import SemanticWorkspace from './components/SemanticWorkspace';
import CADViewer from './components/CADViewer';
import ManufacturingPanel from './components/ManufacturingPanel';
import CollaborationPanel from './components/CollaborationPanel';

type PanelKey = 'workspace' | 'manufacturing' | 'collaboration';

const PANEL_LABELS: Record<PanelKey, string> = {
  workspace: '✏️ Workspace',
  manufacturing: '⚙️ Manufacturing',
  collaboration: '👥 Collaboration',
};

const App: React.FC = () => {
  const [activePanel, setActivePanel] = useState<PanelKey>('workspace');

  return (
    <div className="flex flex-col h-screen bg-zinc-950 text-gray-100 overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-2 bg-zinc-900 border-b border-zinc-800 shrink-0">
        <div className="flex items-center gap-3">
          <svg className="w-7 h-7 text-sky-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
          </svg>
          <span className="font-bold text-xl text-white tracking-tight">Text-to-CAD</span>
          <span className="text-xs text-zinc-500 hidden sm:inline">AI-powered 3D CAD generation</span>
        </div>
        <div className="flex items-center gap-1 text-xs text-zinc-500">
          <span className="w-2 h-2 bg-green-500 rounded-full inline-block" />
          API Ready
        </div>
      </header>

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar */}
        <aside className="w-80 shrink-0 flex flex-col border-r border-zinc-800 overflow-hidden">
          {/* Panel tabs */}
          <div className="flex border-b border-zinc-800">
            {(Object.keys(PANEL_LABELS) as PanelKey[]).map((key) => (
              <button
                key={key}
                onClick={() => setActivePanel(key)}
                className={`flex-1 py-2 text-xs font-medium transition-colors ${
                  activePanel === key
                    ? 'border-b-2 border-sky-500 text-sky-400'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                {PANEL_LABELS[key]}
              </button>
            ))}
          </div>

          {/* Active panel */}
          <div className="flex-1 overflow-y-auto">
            {activePanel === 'workspace' && <SemanticWorkspace />}
            {activePanel === 'manufacturing' && <ManufacturingPanel />}
            {activePanel === 'collaboration' && <CollaborationPanel />}
          </div>
        </aside>

        {/* 3D Viewport */}
        <main className="flex-1 overflow-hidden">
          <CADViewer />
        </main>
      </div>

      {/* Footer */}
      <footer className="px-4 py-1.5 bg-zinc-900 border-t border-zinc-800 shrink-0 flex items-center justify-between text-xs text-zinc-600">
        <span>Coordinate system: X+ Right · Y+ Back · Z+ Up (mm)</span>
        <span>Text-to-CAD v1.0.0 · FastAPI + React Three Fiber</span>
      </footer>
    </div>
  );
};

export default App;

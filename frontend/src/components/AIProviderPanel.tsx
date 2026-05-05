import React, { useState } from 'react';
import useCADStore from '../store/cadStore';
import { AIProvider, AIProviderConfig } from '../types/cad';

// ------------------------------------------------------------------ //
// Static provider metadata (mirrors backend PROVIDER_INFO)            //
// ------------------------------------------------------------------ //

const PROVIDERS: {
  provider: AIProvider;
  label: string;
  description: string;
  requiresKey: boolean;
  requiresBaseUrl: boolean;
  defaultModel: string | null;
  modelPlaceholder?: string;
}[] = [
  {
    provider: AIProvider.RULES,
    label: '🔢 Rule-Based (no key needed)',
    description: 'Fast, offline pattern matcher. Works without any API key.',
    requiresKey: false,
    requiresBaseUrl: false,
    defaultModel: null,
  },
  {
    provider: AIProvider.OPENAI,
    label: '🤖 OpenAI (GPT-4o, GPT-4, …)',
    description: 'Use OpenAI GPT models. Requires an OpenAI API key.',
    requiresKey: true,
    requiresBaseUrl: false,
    defaultModel: 'gpt-4o',
    modelPlaceholder: 'gpt-4o',
  },
  {
    provider: AIProvider.ANTHROPIC,
    label: '🟤 Anthropic (Claude)',
    description: 'Use Anthropic Claude models. Requires an Anthropic API key.',
    requiresKey: true,
    requiresBaseUrl: false,
    defaultModel: 'claude-3-5-sonnet-20241022',
    modelPlaceholder: 'claude-3-5-sonnet-20241022',
  },
  {
    provider: AIProvider.GOOGLE,
    label: '🔵 Google (Gemini)',
    description: 'Use Google Gemini models. Requires a Google AI API key.',
    requiresKey: true,
    requiresBaseUrl: false,
    defaultModel: 'gemini-1.5-flash',
    modelPlaceholder: 'gemini-1.5-flash',
  },
  {
    provider: AIProvider.OLLAMA,
    label: '🦙 Ollama (local)',
    description:
      'Run models locally with Ollama. No API key needed. Backend must reach Ollama.',
    requiresKey: false,
    requiresBaseUrl: false,
    defaultModel: 'llama3',
    modelPlaceholder: 'llama3',
  },
  {
    provider: AIProvider.CUSTOM,
    label: '🔧 Custom (OpenAI-compatible)',
    description:
      'Any OpenAI-compatible endpoint: LM Studio, vLLM, Together AI, etc.',
    requiresKey: false,
    requiresBaseUrl: true,
    defaultModel: null,
    modelPlaceholder: 'model-name',
  },
];

// ------------------------------------------------------------------ //
// Component                                                           //
// ------------------------------------------------------------------ //

export const AIProviderPanel: React.FC = () => {
  const { aiProvider, setAIProvider } = useCADStore();

  const [selectedProvider, setSelectedProvider] = useState<AIProvider>(
    aiProvider.provider,
  );
  const [apiKey, setApiKey] = useState(aiProvider.api_key ?? '');
  const [model, setModel] = useState(aiProvider.model ?? '');
  const [baseUrl, setBaseUrl] = useState(aiProvider.base_url ?? '');
  const [saved, setSaved] = useState(false);

  const info = PROVIDERS.find((p) => p.provider === selectedProvider)!;

  const handleSave = () => {
    const config: AIProviderConfig = {
      provider: selectedProvider,
      api_key: apiKey || undefined,
      model: model || undefined,
      base_url: baseUrl || undefined,
    };
    setAIProvider(config);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleProviderChange = (p: AIProvider) => {
    setSelectedProvider(p);
    setApiKey('');
    setModel('');
    setBaseUrl('');
    setSaved(false);
  };

  return (
    <div className="panel flex flex-col gap-4 p-4 h-full overflow-y-auto">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-sky-400">AI Provider</h2>
        <p className="text-xs text-zinc-500 mt-0.5">
          Choose which AI backend powers the NLP parser. API keys are sent
          with each request and are never stored on the server.
        </p>
      </div>

      {/* Provider selector */}
      <div>
        <label className="label">Provider</label>
        <div className="flex flex-col gap-1.5">
          {PROVIDERS.map((p) => (
            <button
              key={p.provider}
              onClick={() => handleProviderChange(p.provider)}
              className={`w-full text-left px-3 py-2.5 rounded-lg border text-xs transition-colors ${
                selectedProvider === p.provider
                  ? 'border-sky-500 bg-sky-900/30 text-sky-300'
                  : 'border-zinc-700 bg-zinc-800 text-zinc-300 hover:border-zinc-500 hover:text-zinc-100'
              }`}
            >
              <div className="font-medium">{p.label}</div>
              <div className="text-zinc-500 mt-0.5 leading-4">{p.description}</div>
            </button>
          ))}
        </div>
      </div>

      {/* API Key */}
      {info.requiresKey && (
        <div>
          <label className="label">API Key</label>
          <input
            type="password"
            className="input"
            placeholder="Paste your API key…"
            value={apiKey}
            onChange={(e) => { setApiKey(e.target.value); setSaved(false); }}
            autoComplete="off"
          />
          <p className="text-xs text-zinc-600 mt-1">
            Sent only with generation requests. Not stored or logged.
          </p>
        </div>
      )}

      {/* Base URL (Ollama / Custom) */}
      {(info.requiresBaseUrl || selectedProvider === AIProvider.OLLAMA) && (
        <div>
          <label className="label">
            Base URL{' '}
            {selectedProvider === AIProvider.OLLAMA && (
              <span className="text-zinc-600 font-normal">(optional)</span>
            )}
          </label>
          <input
            type="text"
            className="input"
            placeholder={
              selectedProvider === AIProvider.OLLAMA
                ? 'http://localhost:11434/v1'
                : 'https://your-api/v1'
            }
            value={baseUrl}
            onChange={(e) => { setBaseUrl(e.target.value); setSaved(false); }}
          />
        </div>
      )}

      {/* Model override */}
      {selectedProvider !== AIProvider.RULES && (
        <div>
          <label className="label">
            Model{' '}
            <span className="text-zinc-600 font-normal">
              (default: {info.defaultModel ?? 'provider default'})
            </span>
          </label>
          <input
            type="text"
            className="input"
            placeholder={info.modelPlaceholder ?? 'model name'}
            value={model}
            onChange={(e) => { setModel(e.target.value); setSaved(false); }}
          />
        </div>
      )}

      {/* Save */}
      <button
        onClick={handleSave}
        className="btn-primary justify-center py-2 text-sm font-semibold"
      >
        {saved ? '✓ Saved' : 'Apply Settings'}
      </button>

      {/* Active summary */}
      <div className="border border-zinc-700 rounded-lg px-3 py-2.5 bg-zinc-800/40 text-xs text-zinc-400 space-y-1">
        <p className="font-medium text-zinc-300">Active configuration</p>
        <p>
          Provider:{' '}
          <span className="text-sky-400">
            {PROVIDERS.find((p) => p.provider === aiProvider.provider)?.label ??
              aiProvider.provider}
          </span>
        </p>
        {aiProvider.model && (
          <p>
            Model: <span className="text-zinc-300">{aiProvider.model}</span>
          </p>
        )}
        {aiProvider.base_url && (
          <p>
            Base URL: <span className="text-zinc-300 break-all">{aiProvider.base_url}</span>
          </p>
        )}
        {aiProvider.api_key && (
          <p>
            API Key: <span className="text-zinc-300">{'•'.repeat(8)}</span>
          </p>
        )}
      </div>
    </div>
  );
};

export default AIProviderPanel;

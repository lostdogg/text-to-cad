import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import * as api from '../api/client';
import {
  AIProvider,
  AIProviderConfig,
  CADModel,
  CNCParams,
  GenerateResponse,
  LaserParams,
  ManufacturingReport,
  ManufacturingType,
  Participant,
  PrintParams,
  SessionState,
  ValidationResult,
} from '../types/cad';
import type { ToastItem, ToastType } from '../components/Toast';

// ------------------------------------------------------------------ //
// State                                                                //
// ------------------------------------------------------------------ //

interface ManufacturingSettings {
  activeTab: ManufacturingType;
  cncParams: Partial<CNCParams>;
  printParams: Partial<PrintParams>;
  laserParams: Partial<LaserParams>;
}

interface CollaborationState {
  sessionId: string | null;
  participants: Record<string, Participant>;
  isConnected: boolean;
  chat: Array<{ participant_id: string; message: string; timestamp: string; color: string; participant_name: string }>;
  client: api.CollaborationClient | null;
}

interface CADState {
  // Models
  currentModel: CADModel | null;
  models: CADModel[];

  // Generation
  isLoading: boolean;
  error: string | null;
  lastResponse: GenerateResponse | null;

  // Validation
  validation: ValidationResult | null;
  manufacturingReport: ManufacturingReport | null;

  // Manufacturing
  manufacturing: ManufacturingSettings;

  // AI Provider
  aiProvider: AIProviderConfig;

  // Collaboration
  collaboration: CollaborationState;

  // UI
  wireframe: boolean;
  showGrid: boolean;
  measureMode: boolean;

  // Toasts
  toasts: ToastItem[];

  // Agent pipeline logs
  agentLogs: string[];
}

// ------------------------------------------------------------------ //
// Actions                                                              //
// ------------------------------------------------------------------ //

interface CADActions {
  generateFromText: (text: string, manufacturingType?: ManufacturingType) => Promise<void>;
  loadModels: () => Promise<void>;
  setCurrentModel: (model: CADModel | null) => void;
  clearError: () => void;

  exportModel: (format: 'stl' | 'obj' | 'step', modelId: string) => Promise<void>;
  exportGCode: (type: 'cnc' | '3dprint' | 'laser', modelId: string) => Promise<void>;
  downloadReport: (modelId: string) => Promise<void>;

  updateCNCParams: (params: Partial<CNCParams>) => void;
  updatePrintParams: (params: Partial<PrintParams>) => void;
  updateLaserParams: (params: Partial<LaserParams>) => void;
  setManufacturingTab: (tab: ManufacturingType) => void;

  setAIProvider: (config: AIProviderConfig) => void;

  joinSession: (sessionId: string) => void;
  leaveSession: () => void;
  sendChatMessage: (message: string) => void;
  moveCursor: (position: { x: number; y: number; z: number }) => void;

  toggleWireframe: () => void;
  toggleGrid: () => void;
  toggleMeasureMode: () => void;

  addToast: (type: ToastType, message: string) => void;
  removeToast: (id: string) => void;
}

type CADStore = CADState & CADActions;

// ------------------------------------------------------------------ //
// Store                                                                //
// ------------------------------------------------------------------ //

const defaultManufacturing: ManufacturingSettings = {
  activeTab: ManufacturingType.CNC_3AXIS,
  cncParams: { tool_diameter: 6, spindle_speed: 10000, feed_rate: 1000, material: 'aluminum' },
  printParams: { layer_height: 0.2, infill_percent: 20, supports: true, material: 'PLA', printer_type: 'FDM' },
  laserParams: { power: 80, speed: 20, kerf_width: 0.2, material: 'acrylic', passes: 1, sheet_thickness: 3 },
};

const defaultCollaboration: CollaborationState = {
  sessionId: null,
  participants: {},
  isConnected: false,
  chat: [],
  client: null,
};

export const useCADStore = create<CADStore>()(
  devtools(
    (set, get) => ({
      // State
      currentModel: null,
      models: [],
      isLoading: false,
      error: null,
      lastResponse: null,
      validation: null,
      manufacturingReport: null,
      manufacturing: defaultManufacturing,
      aiProvider: { provider: AIProvider.RULES },
      collaboration: defaultCollaboration,
      wireframe: false,
      showGrid: true,
      measureMode: false,
      toasts: [],
      agentLogs: [],

      // ---------------------------------------------------------------- //
      // Generation                                                        //
      // ---------------------------------------------------------------- //
      generateFromText: async (text, manufacturingType) => {
        set({ isLoading: true, error: null, agentLogs: [] });
        try {
          const { aiProvider } = get();
          const response = await api.generate({
            text,
            manufacturing_type: manufacturingType,
            ai_provider: aiProvider.provider !== AIProvider.RULES ? aiProvider : undefined,
          });
          if (!response.success) throw new Error(response.error ?? 'Generation failed');
          const model: CADModel = {
            id: response.model_id,
            name: response.name,
            mesh_data: response.mesh_data,
            source_text: text,
            created_at: new Date().toISOString(),
          };
          set((state) => ({
            currentModel: model,
            models: [model, ...state.models.filter((m) => m.id !== model.id)],
            lastResponse: response,
            validation: response.validation ?? null,
            manufacturingReport: response.manufacturing_report ?? null,
            agentLogs: response.agent_logs ?? [],
            isLoading: false,
          }));
          get().addToast('success', `Model generated in ${response.processing_time.toFixed(2)}s`);
        } catch (err) {
          const msg = String(err);
          set({ error: msg, isLoading: false });
          get().addToast('error', msg.length > 80 ? msg.slice(0, 80) + '…' : msg);
        }
      },

      loadModels: async () => {
        try {
          const { models } = await api.listModels();
          set({ models });
        } catch {/* silent */ }
      },

      setCurrentModel: (model) => set({ currentModel: model }),
      clearError: () => set({ error: null }),

      // ---------------------------------------------------------------- //
      // Exports                                                           //
      // ---------------------------------------------------------------- //
      exportModel: async (format, modelId) => {
        try {
          let blob: Blob;
          let filename: string;
          if (format === 'stl') {
            blob = await api.exportSTL(modelId);
            filename = `model-${modelId}.stl`;
          } else if (format === 'obj') {
            blob = await api.exportOBJ(modelId);
            filename = `model-${modelId}.obj`;
          } else {
            blob = await api.exportSTEP(modelId);
            filename = `model-${modelId}.step`;
          }
          api.downloadBlob(blob, filename);
          get().addToast('success', `Exported ${format.toUpperCase()} successfully`);
        } catch (err) {
          const msg = `Export failed: ${String(err)}`;
          set({ error: msg });
          get().addToast('error', msg);
        }
      },

      exportGCode: async (type, modelId) => {
        try {
          let blob: Blob;
          const { manufacturing } = get();
          if (type === 'cnc') {
            blob = await api.exportGCodeCNC(modelId, manufacturing.cncParams as CNCParams);
          } else if (type === '3dprint') {
            blob = await api.exportGCode3DPrint(modelId, manufacturing.printParams as PrintParams);
          } else {
            blob = await api.exportGCodeLaser(modelId, manufacturing.laserParams as LaserParams);
          }
          api.downloadBlob(blob, `model-${modelId}-${type}.gcode`);
          get().addToast('success', `G-code exported successfully`);
        } catch (err) {
          const msg = `G-code export failed: ${String(err)}`;
          set({ error: msg });
          get().addToast('error', msg);
        }
      },

      downloadReport: async (modelId) => {
        try {
          const report = await api.getQCReport(modelId);
          const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
          api.downloadBlob(blob, `qc-report-${modelId}.json`);
        } catch (err) {
          set({ error: `Report download failed: ${String(err)}` });
        }
      },

      // ---------------------------------------------------------------- //
      // Manufacturing settings                                            //
      // ---------------------------------------------------------------- //
      updateCNCParams: (params) =>
        set((state) => ({
          manufacturing: {
            ...state.manufacturing,
            cncParams: { ...state.manufacturing.cncParams, ...params },
          },
        })),

      updatePrintParams: (params) =>
        set((state) => ({
          manufacturing: {
            ...state.manufacturing,
            printParams: { ...state.manufacturing.printParams, ...params },
          },
        })),

      updateLaserParams: (params) =>
        set((state) => ({
          manufacturing: {
            ...state.manufacturing,
            laserParams: { ...state.manufacturing.laserParams, ...params },
          },
        })),

      setManufacturingTab: (tab) =>
        set((state) => ({
          manufacturing: { ...state.manufacturing, activeTab: tab },
        })),

      setAIProvider: (config) => set({ aiProvider: config }),

      // ---------------------------------------------------------------- //
      // Collaboration                                                     //
      // ---------------------------------------------------------------- //
      joinSession: (sessionId) => {
        const existing = get().collaboration.client;
        existing?.disconnect();

        const client = new api.CollaborationClient(sessionId);

        client.on('welcome', (event) => {
          const sessionState = event['session_state'] as { participants?: Record<string, unknown> } | undefined;
          const participants = (sessionState?.participants ?? {}) as Record<string, import('../types/cad').Participant>;
          set((state) => ({
            collaboration: {
              ...state.collaboration,
              participants,
              isConnected: true,
            },
          }));
        });

        client.on('participant_joined', (event) => {
          const p = event['participant'] as import('../types/cad').Participant;
          set((state) => ({
            collaboration: {
              ...state.collaboration,
              participants: { ...state.collaboration.participants, [p.participant_id]: p },
            },
          }));
        });

        client.on('participant_left', (event) => {
          const pid = event['participant_id'] as string;
          set((state) => {
            const participants = { ...state.collaboration.participants };
            delete participants[pid];
            return { collaboration: { ...state.collaboration, participants } };
          });
        });

        client.on('chat_message', (event) => {
          set((state) => ({
            collaboration: {
              ...state.collaboration,
              chat: [
                ...state.collaboration.chat,
                {
                  participant_id: event['participant_id'] as string,
                  participant_name: event['participant_name'] as string,
                  color: event['color'] as string,
                  message: event['message'] as string,
                  timestamp: event['timestamp'] as string,
                },
              ],
            },
          }));
        });

        client.connect();
        set((state) => ({
          collaboration: { ...state.collaboration, sessionId, client },
        }));
      },

      leaveSession: () => {
        get().collaboration.client?.disconnect();
        set({ collaboration: defaultCollaboration });
      },

      sendChatMessage: (message) => {
        get().collaboration.client?.send({ event_type: 'chat_message', message });
      },

      moveCursor: (position) => {
        get().collaboration.client?.send({ event_type: 'cursor_move', position });
      },

      // ---------------------------------------------------------------- //
      // UI toggles                                                        //
      // ---------------------------------------------------------------- //
      toggleWireframe: () => set((s) => ({ wireframe: !s.wireframe })),
      toggleGrid: () => set((s) => ({ showGrid: !s.showGrid })),
      toggleMeasureMode: () => set((s) => ({ measureMode: !s.measureMode })),

      // ---------------------------------------------------------------- //
      // Toasts                                                            //
      // ---------------------------------------------------------------- //
      addToast: (type, message) => {
        const id = crypto.randomUUID();
        set((s) => ({ toasts: [...s.toasts, { id, type, message }] }));
      },
      removeToast: (id) =>
        set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
    }),
    { name: 'cad-store' },
  ),
);

export default useCADStore;

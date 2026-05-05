import axios, { AxiosInstance } from 'axios';
import {
  CADModel,
  CNCParams,
  GenerateRequest,
  GenerateResponse,
  LaserParams,
  ManufacturingType,
  PrintParams,
} from '../types/cad';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const WS_URL   = import.meta.env.VITE_WS_URL  ?? 'ws://localhost:8000';

const http: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 60_000,
});

// ------------------------------------------------------------------ //
// Generation                                                           //
// ------------------------------------------------------------------ //

export async function generate(req: GenerateRequest): Promise<GenerateResponse> {
  const { data } = await http.post<GenerateResponse>('/api/generate', req);
  return data;
}

export async function listModels(): Promise<{ models: CADModel[]; total: number }> {
  const { data } = await http.get('/api/generate/models');
  return data;
}

export async function getModel(modelId: string): Promise<CADModel> {
  const { data } = await http.get<CADModel>(`/api/generate/models/${modelId}`);
  return data;
}

// ------------------------------------------------------------------ //
// Exports                                                              //
// ------------------------------------------------------------------ //

export async function exportSTL(modelId: string): Promise<Blob> {
  const { data } = await http.post(`/api/export/stl/${modelId}`, {}, { responseType: 'blob' });
  return data as Blob;
}

export async function exportOBJ(modelId: string): Promise<Blob> {
  const { data } = await http.post(`/api/export/obj/${modelId}`, {}, { responseType: 'blob' });
  return data as Blob;
}

export async function exportSTEP(modelId: string): Promise<Blob> {
  const { data } = await http.post(`/api/export/step/${modelId}`, {}, { responseType: 'blob' });
  return data as Blob;
}

export async function exportGCodeCNC(modelId: string, params?: CNCParams): Promise<Blob> {
  const { data } = await http.post(
    `/api/export/gcode/cnc/${modelId}`,
    params ? { params } : {},
    { responseType: 'blob' },
  );
  return data as Blob;
}

export async function exportGCode3DPrint(modelId: string, params?: PrintParams): Promise<Blob> {
  const { data } = await http.post(
    `/api/export/gcode/3dprint/${modelId}`,
    params ? { params } : {},
    { responseType: 'blob' },
  );
  return data as Blob;
}

export async function exportGCodeLaser(modelId: string, params?: LaserParams): Promise<Blob> {
  const { data } = await http.post(
    `/api/export/gcode/laser/${modelId}`,
    params ? { params } : {},
    { responseType: 'blob' },
  );
  return data as Blob;
}

// ------------------------------------------------------------------ //
// Reports                                                              //
// ------------------------------------------------------------------ //

export async function getQCReport(modelId: string): Promise<Record<string, unknown>> {
  const { data } = await http.get(`/api/export/report/${modelId}`);
  return data;
}

export async function getProcurementSpecs(
  modelId: string,
  materials = 'aluminum_6061',
): Promise<Record<string, unknown>> {
  const { data } = await http.get(`/api/export/procurement/${modelId}?materials=${materials}`);
  return data;
}

// ------------------------------------------------------------------ //
// Download helper                                                      //
// ------------------------------------------------------------------ //

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ------------------------------------------------------------------ //
// WebSocket collaboration client                                       //
// ------------------------------------------------------------------ //

export class CollaborationClient {
  private ws: WebSocket | null = null;
  private sessionId: string;
  private listeners: Map<string, ((event: Record<string, unknown>) => void)[]> = new Map();
  public reconnectDelay = 2000;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(sessionId: string) {
    this.sessionId = sessionId;
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;
    this.ws = new WebSocket(`${WS_URL}/api/collaborate/ws/${this.sessionId}`);

    this.ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as Record<string, unknown>;
        const type = event['event_type'] as string;
        const handlers = this.listeners.get(type) ?? [];
        const allHandlers = this.listeners.get('*') ?? [];
        [...handlers, ...allHandlers].forEach((h) => h(event));
      } catch { /* ignore parse errors */ }
    };

    this.ws.onclose = () => {
      this.reconnectTimer = setTimeout(() => this.connect(), this.reconnectDelay);
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }

  send(event: Record<string, unknown>) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(event));
    }
  }

  on(eventType: string, handler: (event: Record<string, unknown>) => void) {
    if (!this.listeners.has(eventType)) this.listeners.set(eventType, []);
    this.listeners.get(eventType)!.push(handler);
  }

  off(eventType: string, handler: (event: Record<string, unknown>) => void) {
    const handlers = this.listeners.get(eventType);
    if (handlers) {
      this.listeners.set(eventType, handlers.filter((h) => h !== handler));
    }
  }

  get isConnected() {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export default http;

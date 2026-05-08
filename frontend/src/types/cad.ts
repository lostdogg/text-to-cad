// ------------------------------------------------------------------ //
// AI Provider types                                                   //
// ------------------------------------------------------------------ //

export enum AIProvider {
  RULES = 'rules',
  OPENAI = 'openai',
  ANTHROPIC = 'anthropic',
  GOOGLE = 'google',
  OLLAMA = 'ollama',
  CUSTOM = 'custom',
}

export interface AIProviderConfig {
  provider: AIProvider;
  api_key?: string;
  model?: string;
  base_url?: string;
}

export interface ProviderInfo {
  provider: AIProvider;
  label: string;
  description: string;
  requires_key: boolean;
  requires_base_url: boolean;
  default_model: string | null;
}

// ------------------------------------------------------------------ //
// Core geometry types                                                  //
// ------------------------------------------------------------------ //

export interface Vector3 {
  x: number;
  y: number;
  z: number;
}

export interface Transform {
  position: Vector3;
  rotation: Vector3; // Euler degrees
  scale: Vector3;
}

export enum PrimitiveType {
  BOX = 'box',
  CYLINDER = 'cylinder',
  SPHERE = 'sphere',
  CONE = 'cone',
  TORUS = 'torus',
}

export interface PrimitiveSpec {
  type: PrimitiveType;
  dimensions: Record<string, number>;
  transform?: Transform;
  name?: string;
}

export enum BooleanOpType {
  UNION = 'union',
  INTERSECTION = 'intersection',
  SUBTRACTION = 'subtraction',
}

export interface BooleanOpSpec {
  operation: BooleanOpType;
  operand_a: number;
  operand_b: number;
  name?: string;
}

export interface GeometrySpec {
  primitives: PrimitiveSpec[];
  operations: BooleanOpSpec[];
  metadata?: Record<string, unknown>;
  description?: string;
}

export interface MeshData {
  vertices: number[][];
  faces: number[][];
  normals: number[][];
  vertex_count: number;
  face_count: number;
}

export interface CADModel {
  id: string;
  name: string;
  description?: string;
  geometry_spec?: GeometrySpec;
  mesh_data?: MeshData;
  source_text?: string;
  created_at: string;
  updated_at?: string;
  tags?: string[];
}

// ------------------------------------------------------------------ //
// Manufacturing types                                                  //
// ------------------------------------------------------------------ //

export enum ManufacturingType {
  CNC_3AXIS = 'cnc_3axis',
  PRINTING_3D = '3d_printing',
  LASER_CUTTING = 'laser_cutting',
}

export interface CNCParams {
  tool_diameter: number;
  spindle_speed: number;
  feed_rate: number;
  material: string;
  operations: string[];
  coolant: boolean;
}

export interface PrintParams {
  layer_height: number;
  infill_percent: number;
  supports: boolean;
  material: string;
  printer_type: string;
  nozzle_temperature: number;
  bed_temperature: number;
}

export interface LaserParams {
  power: number;
  speed: number;
  kerf_width: number;
  material: string;
  passes: number;
  sheet_thickness: number;
}

export type IssueSeverity = 'error' | 'warning' | 'info';

export interface ValidationIssue {
  severity: IssueSeverity;
  code: string;
  message: string;
  location?: Record<string, unknown>;
  suggestion?: string;
}

export interface MeshStats {
  vertex_count: number;
  face_count: number;
  volume: number;
  surface_area: number;
  bounding_box: Record<string, number>;
  is_watertight: boolean;
  is_manifold: boolean;
}

export interface ValidationResult {
  is_valid: boolean;
  issues: ValidationIssue[];
  mesh_stats: MeshStats;
  manufacturing_type?: string;
  min_wall_thickness?: number;
  max_overhang_angle?: number;
}

export interface CostEstimate {
  material_cost: number;
  machine_cost: number;
  labour_cost: number;
  total_cost: number;
  currency: string;
}

export interface TimeEstimate {
  setup_time: number;
  machining_time: number;
  total_time: number;
  notes?: string;
}

export interface ManufacturingReport {
  model_id: string;
  validation?: ValidationResult;
  cnc_params?: CNCParams;
  print_params?: PrintParams;
  laser_params?: LaserParams;
  cost_estimate?: CostEstimate;
  time_estimate?: TimeEstimate;
  recommended_type?: ManufacturingType;
}

// ------------------------------------------------------------------ //
// API types                                                            //
// ------------------------------------------------------------------ //

export interface GenerateRequest {
  text: string;
  manufacturing_type?: ManufacturingType;
  options?: Record<string, unknown>;
  ai_provider?: AIProviderConfig;
}

export interface GenerateResponse {
  model_id: string;
  name: string;
  created_at?: string;
  mesh_data?: MeshData;
  validation?: ValidationResult;
  manufacturing_report?: ManufacturingReport;
  processing_time: number;
  agent_logs: string[];
  success: boolean;
  error?: string;
}

// ------------------------------------------------------------------ //
// Collaboration types                                                  //
// ------------------------------------------------------------------ //

export interface Participant {
  participant_id: string;
  name: string;
  color: string;
  cursor_position?: Vector3;
  joined_at?: string;
}

export type CollaborationEventType =
  | 'welcome'
  | 'participant_joined'
  | 'participant_left'
  | 'update_model'
  | 'cursor_move'
  | 'chat_message'
  | 'ping'
  | 'pong';

export interface CollaborationEvent {
  event_type: CollaborationEventType;
  session_id: string;
  participant_id?: string;
  payload?: Record<string, unknown>;
  timestamp: string;
  [key: string]: unknown;
}

export interface ChatMessage {
  participant_id: string;
  participant_name: string;
  color: string;
  message: string;
  timestamp: string;
}

export interface SessionState {
  session_id: string;
  participants: Record<string, Participant>;
  chat: ChatMessage[];
  created_at: string;
}

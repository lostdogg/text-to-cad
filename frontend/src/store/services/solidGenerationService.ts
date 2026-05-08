import * as api from '../../api/client';
import { AIProvider, AIProviderConfig, CADModel, GenerateResponse, ManufacturingType } from '../../types/cad';

export interface GenerationResult {
  response: GenerateResponse;
  model: CADModel;
}

export async function generateSolidModel(
  text: string,
  aiProvider: AIProviderConfig,
  manufacturingType?: ManufacturingType,
): Promise<GenerationResult> {
  const response = await api.generate({
    text,
    manufacturing_type: manufacturingType,
    ai_provider: aiProvider.provider !== AIProvider.RULES ? aiProvider : undefined,
  });
  if (!response.success) {
    throw new Error(response.error ?? 'Generation failed');
  }
  const model: CADModel = {
    id: response.model_id,
    name: response.name,
    mesh_data: response.mesh_data,
    source_text: text,
    created_at: new Date().toISOString(),
  };
  return { response, model };
}

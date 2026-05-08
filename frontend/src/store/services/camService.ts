import * as api from '../../api/client';
import { CNCParams, LaserParams, PrintParams } from '../../types/cad';

export async function exportSolid(
  format: 'stl' | 'obj' | 'step',
  modelId: string,
): Promise<{ blob: Blob; filename: string }> {
  if (format === 'stl') return { blob: await api.exportSTL(modelId), filename: `model-${modelId}.stl` };
  if (format === 'obj') return { blob: await api.exportOBJ(modelId), filename: `model-${modelId}.obj` };
  return { blob: await api.exportSTEP(modelId), filename: `model-${modelId}.step` };
}

export async function exportCamGCode(
  type: 'cnc' | '3dprint' | 'laser',
  modelId: string,
  params: {
    cncParams: Partial<CNCParams>;
    printParams: Partial<PrintParams>;
    laserParams: Partial<LaserParams>;
  },
): Promise<Blob> {
  if (type === 'cnc') {
    return api.exportGCodeCNC(modelId, params.cncParams as CNCParams);
  }
  if (type === '3dprint') {
    return api.exportGCode3DPrint(modelId, params.printParams as PrintParams);
  }
  return api.exportGCodeLaser(modelId, params.laserParams as LaserParams);
}

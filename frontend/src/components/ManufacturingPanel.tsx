import React from 'react';
import useCADStore from '../store/cadStore';
import { ManufacturingType, ValidationIssue } from '../types/cad';

// ------------------------------------------------------------------ //
// Severity badge                                                       //
// ------------------------------------------------------------------ //

function IssueBadge({ issue }: { issue: ValidationIssue }) {
  const cls =
    issue.severity === 'error' ? 'badge-error' :
    issue.severity === 'warning' ? 'badge-warning' : 'badge-info';
  const icon =
    issue.severity === 'error' ? '✕' :
    issue.severity === 'warning' ? '⚠' : 'ℹ';
  return (
    <div className={`${cls} flex flex-col gap-0.5 text-left`}>
      <div className="flex items-center gap-1 font-medium">
        <span>{icon}</span>
        <span>[{issue.code}]</span>
      </div>
      <p className="font-normal ml-4">{issue.message}</p>
      {issue.suggestion && (
        <p className="font-normal ml-4 opacity-75 text-xs">→ {issue.suggestion}</p>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ //
// CNC Tab                                                              //
// ------------------------------------------------------------------ //

function CNCTab() {
  const { manufacturing, updateCNCParams, currentModel, exportGCode } = useCADStore();
  const { cncParams } = manufacturing;
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Tool Diameter (mm)</label>
          <input type="number" className="input" value={cncParams.tool_diameter ?? 6}
            onChange={(e) => updateCNCParams({ tool_diameter: Number(e.target.value) })} />
        </div>
        <div>
          <label className="label">Spindle (RPM)</label>
          <input type="number" className="input" value={cncParams.spindle_speed ?? 10000}
            onChange={(e) => updateCNCParams({ spindle_speed: Number(e.target.value) })} />
        </div>
        <div>
          <label className="label">Feed Rate (mm/min)</label>
          <input type="number" className="input" value={cncParams.feed_rate ?? 1000}
            onChange={(e) => updateCNCParams({ feed_rate: Number(e.target.value) })} />
        </div>
        <div>
          <label className="label">Material</label>
          <select className="input" value={cncParams.material ?? 'aluminum'}
            onChange={(e) => updateCNCParams({ material: e.target.value })}>
            <option value="aluminum">Aluminum 6061</option>
            <option value="steel">Steel 1018</option>
            <option value="plastic">Plastic / Delrin</option>
            <option value="wood">Wood / MDF</option>
          </select>
        </div>
      </div>
      <button
        disabled={!currentModel}
        className="btn-primary justify-center"
        onClick={() => currentModel && exportGCode('cnc', currentModel.id)}
      >
        Export CNC G-code
      </button>
    </div>
  );
}

// ------------------------------------------------------------------ //
// 3D Print Tab                                                         //
// ------------------------------------------------------------------ //

function PrintTab() {
  const { manufacturing, updatePrintParams, currentModel, exportGCode } = useCADStore();
  const { printParams } = manufacturing;
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Layer Height (mm)</label>
          <input type="number" step="0.05" className="input" value={printParams.layer_height ?? 0.2}
            onChange={(e) => updatePrintParams({ layer_height: Number(e.target.value) })} />
        </div>
        <div>
          <label className="label">Infill (%)</label>
          <input type="number" min="5" max="100" className="input" value={printParams.infill_percent ?? 20}
            onChange={(e) => updatePrintParams({ infill_percent: Number(e.target.value) })} />
        </div>
        <div>
          <label className="label">Material</label>
          <select className="input" value={printParams.material ?? 'PLA'}
            onChange={(e) => updatePrintParams({ material: e.target.value })}>
            <option value="PLA">PLA</option>
            <option value="ABS">ABS</option>
            <option value="PETG">PETG</option>
            <option value="Nylon">Nylon</option>
            <option value="Resin">Resin (SLA)</option>
          </select>
        </div>
        <div>
          <label className="label">Printer Type</label>
          <select className="input" value={printParams.printer_type ?? 'FDM'}
            onChange={(e) => updatePrintParams({ printer_type: e.target.value })}>
            <option value="FDM">FDM</option>
            <option value="SLA">SLA</option>
            <option value="SLS">SLS</option>
          </select>
        </div>
        <div>
          <label className="label">Nozzle Temp (°C)</label>
          <input type="number" className="input" value={printParams.nozzle_temperature ?? 200}
            onChange={(e) => updatePrintParams({ nozzle_temperature: Number(e.target.value) })} />
        </div>
        <div>
          <label className="label">Bed Temp (°C)</label>
          <input type="number" className="input" value={printParams.bed_temperature ?? 60}
            onChange={(e) => updatePrintParams({ bed_temperature: Number(e.target.value) })} />
        </div>
      </div>
      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={printParams.supports ?? true}
          onChange={(e) => updatePrintParams({ supports: e.target.checked })}
          className="rounded" />
        <span className="text-sm text-zinc-300">Generate supports</span>
      </label>
      <button
        disabled={!currentModel}
        className="btn-primary justify-center"
        onClick={() => currentModel && exportGCode('3dprint', currentModel.id)}
      >
        Export 3D Print G-code
      </button>
    </div>
  );
}

// ------------------------------------------------------------------ //
// Laser Tab                                                            //
// ------------------------------------------------------------------ //

function LaserTab() {
  const { manufacturing, updateLaserParams, currentModel, exportGCode } = useCADStore();
  const { laserParams } = manufacturing;
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Power (%)</label>
          <input type="number" min="1" max="100" className="input" value={laserParams.power ?? 80}
            onChange={(e) => updateLaserParams({ power: Number(e.target.value) })} />
        </div>
        <div>
          <label className="label">Speed (mm/s)</label>
          <input type="number" className="input" value={laserParams.speed ?? 20}
            onChange={(e) => updateLaserParams({ speed: Number(e.target.value) })} />
        </div>
        <div>
          <label className="label">Kerf Width (mm)</label>
          <input type="number" step="0.01" className="input" value={laserParams.kerf_width ?? 0.2}
            onChange={(e) => updateLaserParams({ kerf_width: Number(e.target.value) })} />
        </div>
        <div>
          <label className="label">Passes</label>
          <input type="number" min="1" max="10" className="input" value={laserParams.passes ?? 1}
            onChange={(e) => updateLaserParams({ passes: Number(e.target.value) })} />
        </div>
        <div>
          <label className="label">Sheet Thickness (mm)</label>
          <input type="number" step="0.5" className="input" value={laserParams.sheet_thickness ?? 3}
            onChange={(e) => updateLaserParams({ sheet_thickness: Number(e.target.value) })} />
        </div>
        <div>
          <label className="label">Material</label>
          <select className="input" value={laserParams.material ?? 'acrylic'}
            onChange={(e) => updateLaserParams({ material: e.target.value })}>
            <option value="acrylic">Acrylic</option>
            <option value="plywood">Plywood</option>
            <option value="steel_sheet">Steel Sheet</option>
            <option value="aluminum_sheet">Aluminum Sheet</option>
          </select>
        </div>
      </div>
      <button
        disabled={!currentModel}
        className="btn-primary justify-center"
        onClick={() => currentModel && exportGCode('laser', currentModel.id)}
      >
        Export Laser G-code
      </button>
    </div>
  );
}

// ------------------------------------------------------------------ //
// Main panel                                                           //
// ------------------------------------------------------------------ //

const TABS = [
  { key: ManufacturingType.CNC_3AXIS, label: '⚙️ CNC' },
  { key: ManufacturingType.PRINTING_3D, label: '🖨 3D Print' },
  { key: ManufacturingType.LASER_CUTTING, label: '🔴 Laser' },
];

export const ManufacturingPanel: React.FC = () => {
  const { manufacturing, setManufacturingTab, validation, manufacturingReport, currentModel, exportModel, downloadReport } = useCADStore();

  return (
    <div className="panel flex flex-col gap-0 h-full overflow-y-auto">
      {/* SW PropertyManager-style section header */}
      <div className="cad-section-header">
        <svg className="w-3 h-3 text-sky-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        CAM / Manufacturing
      </div>

      <div className="flex flex-col gap-4 p-4">

      {/* Tabs */}
      <div className="flex gap-0.5 bg-zinc-950 rounded-sm p-0.5 border border-zinc-600">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setManufacturingTab(tab.key)}
            className={`flex-1 py-1.5 rounded-sm text-xs font-semibold transition-colors ${
              manufacturing.activeTab === tab.key
                ? 'bg-sky-600 text-white'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div>
        {manufacturing.activeTab === ManufacturingType.CNC_3AXIS && <CNCTab />}
        {manufacturing.activeTab === ManufacturingType.PRINTING_3D && <PrintTab />}
        {manufacturing.activeTab === ManufacturingType.LASER_CUTTING && <LaserTab />}
      </div>

      {/* Cost / Time estimate */}
      {manufacturingReport?.cost_estimate && (
        <div className="bg-zinc-800 rounded p-3 space-y-1 text-sm">
          <p className="text-zinc-400 font-medium mb-2">Cost Estimate</p>
          <div className="flex justify-between">
            <span className="text-zinc-500">Material</span>
            <span className="text-zinc-300">${manufacturingReport.cost_estimate.material_cost.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-zinc-500">Machine time</span>
            <span className="text-zinc-300">${manufacturingReport.cost_estimate.machine_cost.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-zinc-500">Labour</span>
            <span className="text-zinc-300">${manufacturingReport.cost_estimate.labour_cost.toFixed(2)}</span>
          </div>
          <div className="flex justify-between font-semibold border-t border-zinc-700 pt-1 mt-1">
            <span className="text-zinc-300">Total</span>
            <span className="text-sky-400">${manufacturingReport.cost_estimate.total_cost.toFixed(2)}</span>
          </div>
          {manufacturingReport.time_estimate && (
            <p className="text-xs text-zinc-500 pt-1">
              ⏱ {manufacturingReport.time_estimate.total_time.toFixed(1)} min total
            </p>
          )}
        </div>
      )}

      {/* Validation issues */}
      {validation && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="label !mb-0">Validation</label>
            <span className={validation.is_valid ? 'badge-ok' : 'badge-error'}>
              {validation.is_valid ? '✓ Valid' : '✕ Issues found'}
            </span>
          </div>
          {validation.mesh_stats && (
            <div className="text-xs text-zinc-500 grid grid-cols-2 gap-x-4 gap-y-0.5 mb-2">
              <span>Vertices: {validation.mesh_stats.vertex_count.toLocaleString()}</span>
              <span>Faces: {validation.mesh_stats.face_count.toLocaleString()}</span>
              <span>Watertight: {validation.mesh_stats.is_watertight ? '✓' : '✕'}</span>
              <span>Volume: {validation.mesh_stats.volume.toFixed(1)} mm³</span>
            </div>
          )}
          {validation.issues.length > 0 ? (
            <div className="flex flex-col gap-1.5">
              {validation.issues.map((issue, i) => (
                <IssueBadge key={i} issue={issue} />
              ))}
            </div>
          ) : (
            <p className="text-xs text-green-400">No issues detected ✓</p>
          )}
        </div>
      )}

      {/* Export mesh buttons */}
      {currentModel && (
        <div>
          <label className="label">Export Mesh</label>
          <div className="flex gap-2">
            {(['stl', 'obj', 'step'] as const).map((fmt) => (
              <button
                key={fmt}
                className="btn-secondary flex-1 text-xs justify-center"
                onClick={() => exportModel(fmt, currentModel.id)}
              >
                {fmt.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Reports */}
      {currentModel && (
        <div>
          <label className="label">Reports & Specs</label>
          <div className="flex flex-col gap-2">
            <button
              className="btn-secondary justify-center text-xs"
              onClick={() => downloadReport(currentModel.id)}
            >
              📋 Download QC Report (JSON)
            </button>
            <a
              href={`/api/export/procurement/${currentModel.id}?materials=aluminum_6061`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-secondary justify-center text-xs text-center"
            >
              🛒 Procurement Specs (McMaster / DigiKey)
            </a>
          </div>
        </div>
      )}
      </div>
    </div>
  );
};

export default ManufacturingPanel;

export interface ViewState {
  wireframe: boolean;
  showGrid: boolean;
  measureMode: boolean;
}

export function toggleWireframe(state: ViewState): Pick<ViewState, 'wireframe'> {
  return { wireframe: !state.wireframe };
}

export function toggleGrid(state: ViewState): Pick<ViewState, 'showGrid'> {
  return { showGrid: !state.showGrid };
}

export function toggleMeasureMode(state: ViewState): Pick<ViewState, 'measureMode'> {
  return { measureMode: !state.measureMode };
}

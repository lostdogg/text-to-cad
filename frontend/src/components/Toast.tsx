import React, { useEffect } from 'react';

export type ToastType = 'success' | 'error' | 'info';

export interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastContainerProps {
  toasts: ToastItem[];
  onRemove: (id: string) => void;
}

export const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, onRemove }) => (
  <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
    {toasts.map((toast) => (
      <ToastMessage key={toast.id} toast={toast} onRemove={onRemove} />
    ))}
  </div>
);

function ToastMessage({ toast, onRemove }: { toast: ToastItem; onRemove: (id: string) => void }) {
  useEffect(() => {
    const timer = setTimeout(() => onRemove(toast.id), 4500);
    return () => clearTimeout(timer);
  }, [toast.id, onRemove]);

  const styles =
    toast.type === 'success'
      ? 'bg-green-900/90 border-green-700 text-green-200'
      : toast.type === 'error'
      ? 'bg-red-900/90 border-red-700 text-red-200'
      : 'bg-zinc-800/90 border-zinc-600 text-zinc-200';

  const icon = toast.type === 'success' ? '✓' : toast.type === 'error' ? '✕' : 'ℹ';

  return (
    <div
      className={`pointer-events-auto flex items-start gap-2 px-4 py-3 rounded-lg border shadow-xl backdrop-blur-sm text-sm max-w-sm toast-slide-in ${styles}`}
    >
      <span className="font-bold shrink-0 mt-0.5">{icon}</span>
      <span className="flex-1">{toast.message}</span>
      <button
        onClick={() => onRemove(toast.id)}
        className="opacity-50 hover:opacity-100 transition-opacity ml-1 shrink-0 text-xs"
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  );
}

export default ToastContainer;

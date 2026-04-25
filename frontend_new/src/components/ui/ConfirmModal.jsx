import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle } from 'lucide-react';
import { Button } from './button';

/**
 * ConfirmModal - A proper React confirmation dialog, NOT window.confirm.
 * Use the `useConfirm` hook to show it.
 * 
 * Usage:
 *   const { confirm, ConfirmModalComponent } = useConfirm();
 *   // In JSX: {ConfirmModalComponent}
 *   // To show: const yes = await confirm({ title: '...', message: '...' });
 */

export function useConfirm() {
  const [state, setState] = useState({ open: false, title: '', message: '', resolve: null });

  const confirm = ({ title, message }) =>
    new Promise((resolve) => {
      setState({ open: true, title, message, resolve });
    });

  const handleYes = () => {
    state.resolve(true);
    setState(s => ({ ...s, open: false }));
  };

  const handleNo = () => {
    state.resolve(false);
    setState(s => ({ ...s, open: false }));
  };

  const ConfirmModalComponent = state.open ? createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={handleNo} />
      {/* Dialog */}
      <div className="relative bg-background border border-border rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4 z-10">
        <div className="flex items-center gap-3 mb-3">
          <div className="h-10 w-10 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center shrink-0">
            <AlertTriangle className="h-5 w-5 text-amber-600" />
          </div>
          <h3 className="font-bold text-base text-foreground">{state.title}</h3>
        </div>
        <p className="text-sm text-muted-foreground mb-5 ml-13">{state.message}</p>
        <div className="flex gap-2 justify-end">
          <Button variant="outline" onClick={handleNo}>Cancel</Button>
          <Button variant="destructive" onClick={handleYes}>Confirm</Button>
        </div>
      </div>
    </div>,
    document.body
  ) : null;

  return { confirm, ConfirmModalComponent };
}

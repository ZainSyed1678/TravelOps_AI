import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('UI ErrorBoundary caught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 my-6 max-w-xl mx-auto rounded-2xl bg-slate-900 border border-red-500/40 shadow-2xl text-center">
          <div className="w-12 h-12 rounded-full bg-red-500/10 text-red-400 flex items-center justify-center mx-auto mb-4 text-2xl border border-red-500/20">
            ⚠️
          </div>
          <h3 className="text-base font-bold text-white mb-2">Display Rendering Error</h3>
          <p className="text-xs text-slate-400 mb-4">
            A component encounter a display error. The application recovered without crashing.
          </p>
          <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 font-mono text-[11px] text-red-400 text-left overflow-x-auto mb-6">
            {this.state.error?.message || 'Unknown render exception'}
          </div>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
            className="px-5 py-2.5 rounded-xl text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white transition-colors shadow-lg shadow-sky-900/40"
          >
            Reload Interface
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

import React from "react";

type ErrorBoundaryState = {
  hasError: boolean;
  error?: Error;
};

type ErrorBoundaryProps = React.PropsWithChildren;

export default class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("UI crashed", error, info);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: undefined });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="app">
          <main className="content">
            <div className="card stack">
              <h2>Something went wrong</h2>
              <div className="muted">The console hit an unexpected error.</div>
              {this.state.error?.message && <div className="error">{this.state.error.message}</div>}
              <div className="row">
                <button onClick={this.handleReload}>Reload</button>
              </div>
            </div>
          </main>
        </div>
      );
    }

    return this.props.children;
  }
}

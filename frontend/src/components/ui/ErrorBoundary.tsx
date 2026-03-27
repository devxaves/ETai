"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children?: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export default class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("UI Error caught:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="flex flex-col items-center justify-center p-6 border border-[#2a2a2a] bg-[#1a1a1a] rounded-lg">
          <h2 className="text-red-400 font-semibold mb-2">Something went wrong</h2>
          <p className="text-[#888888] text-sm mb-4 text-center">
            {this.state.error?.message || "An unexpected error occurred building this UI component."}
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false });
              this.props.onReset?.();
            }}
            className="px-4 py-2 bg-[#2a2a2a] hover:bg-[#333333] transition-colors rounded text-sm text-white"
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Log the error details
    console.error('App crashed:', error, errorInfo);
    this.setState({
      error: error,
      errorInfo: errorInfo
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-red-50 flex items-center justify-center p-4">
          <div className="bg-white p-8 rounded-lg shadow-lg max-w-2xl w-full">
            <div className="flex items-center mb-4">
              <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mr-4">
                <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L4.268 19.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold text-red-600">
                  Horary Master - Application Error
                </h1>
                <p className="text-gray-600">
                  The application encountered an unexpected error
                </p>
              </div>
            </div>
            
            <div className="mb-6">
              <h2 className="text-lg font-semibold mb-2">What happened?</h2>
              <p className="text-gray-600 mb-4">
                The app crashed while loading. This could be due to:
              </p>
              <ul className="list-disc list-inside text-gray-600 space-y-1 mb-4">
                <li>Browser compatibility issues</li>
                <li>JavaScript syntax errors</li>
                <li>Missing dependencies</li>
                <li>API connection problems</li>
              </ul>
            </div>

            {this.state.error && (
              <div className="mb-6">
                <h3 className="text-md font-semibold mb-2">Error Details:</h3>
                <div className="bg-gray-100 p-3 rounded text-sm font-mono overflow-auto max-h-32">
                  {this.state.error.toString()}
                </div>
              </div>
            )}

            {this.state.errorInfo && (
              <details className="mb-6">
                <summary className="cursor-pointer text-md font-semibold mb-2">
                  Stack Trace (Click to expand)
                </summary>
                <div className="bg-gray-100 p-3 rounded text-xs font-mono overflow-auto max-h-48">
                  {this.state.errorInfo.componentStack}
                </div>
              </details>
            )}

            <div className="flex space-x-4">
              <button 
                className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-2 rounded transition-colors"
                onClick={() => window.location.reload()}
              >
                Reload Application
              </button>
              <button 
                className="bg-gray-500 hover:bg-gray-600 text-white px-6 py-2 rounded transition-colors"
                onClick={() => {
                  // Clear local storage in case it's causing issues
                  localStorage.clear();
                  window.location.reload();
                }}
              >
                Reset & Reload
              </button>
            </div>

            <div className="mt-6 pt-4 border-t border-gray-200">
              <p className="text-sm text-gray-500">
                💡 <strong>Tip:</strong> Open browser DevTools (F12) → Console tab for more detailed error information
              </p>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
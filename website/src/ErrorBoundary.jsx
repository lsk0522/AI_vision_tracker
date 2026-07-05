import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', color: 'red', backgroundColor: '#fee' }}>
          <h2>Something went wrong in the 3D Viewer.</h2>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{this.state.error?.toString()}</pre>
        </div>
      );
    }
    return <div style={{width:'100%',height:'100%'}}>{this.props.children}</div>;
  }
}

export default ErrorBoundary;

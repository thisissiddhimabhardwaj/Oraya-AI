import { Component } from "react";
export default class AppErrorBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <main className="min-h-screen grid place-items-center bg-cream p-8">
          <section className="max-w-md">
            <p className="eyebrow">ORAYA · A MOMENT TO RESET</p>
            <h1 className="font-display text-4xl my-4">
              Let’s find our place again.
            </h1>
            <p className="text-sm text-muted mb-6">
              Your saved learning is still on the server. Reload this page to
              continue.
            </p>
            <button
              className="btn btn-primary"
              onClick={() => window.location.reload()}
            >
              Reload your learning space
            </button>
          </section>
        </main>
      );
    return this.props.children;
  }
}

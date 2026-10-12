import Link from "next/link";

export default function NotFound() {
  return (
    <div className="stack">
      <h1>Page not found</h1>
      <p>That address is not part of ElectionSimulationAI.</p>
      <Link className="button" href="/">
        Go to the home page
      </Link>
    </div>
  );
}

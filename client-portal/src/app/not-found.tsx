import Link from "next/link";

export default function NotFound() {
  return (
    <div
      className="flex flex-col items-center justify-center min-h-screen px-6 text-center"
      style={{ background: "#0A0F1C" }}
    >
      {/* Large 404 text */}
      <div
        className="text-[120px] sm:text-[160px] font-black leading-none select-none mb-4"
        style={{
          background: "linear-gradient(135deg, rgba(108,99,255,0.3), rgba(0,212,170,0.3))",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
        }}
      >
        404
      </div>

      <h1 className="text-2xl font-bold text-white mb-2">Page not found</h1>
      <p className="text-sm text-[#6B7280] mb-8 max-w-md">
        The page you are looking for does not exist or has been moved.
      </p>

      <Link
        href="/"
        className="px-6 py-3 rounded-xl text-sm font-semibold text-white transition-opacity hover:opacity-90"
        style={{ background: "linear-gradient(135deg, #FF6D5A, #FF8A6B)" }}
      >
        Go Home
      </Link>
    </div>
  );
}

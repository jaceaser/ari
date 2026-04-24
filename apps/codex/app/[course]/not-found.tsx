export default function NotFound() {
  return (
    <div
      className="flex h-screen w-full flex-col items-center justify-center bg-[#080808]"
      style={{ fontFamily: 'system-ui, sans-serif' }}
    >
      <div style={{ color: 'hsl(41 92% 67%)', fontSize: 48, fontWeight: 900 }}>404</div>
      <div style={{ color: 'rgba(255,255,255,0.4)', marginTop: 8 }}>Course not found.</div>
    </div>
  );
}

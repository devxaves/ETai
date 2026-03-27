export default function RadarPage() {
  return (
    <div className="h-full flex flex-col pt-4 px-4 overflow-hidden">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight uppercase flex items-center gap-2">
            Opportunity Radar
            <span className="bg-red-500 text-white text-[10px] uppercase font-bold py-0.5 px-1.5 rounded tracking-widest inline-flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-white pulse-live block"></span>
              Live Feed
            </span>
          </h1>
          <p className="text-[#888888] text-sm mt-1">
            Real-time composite signals derived from SEBI bulk/block deals, insider filings, and sentiment analysis.
          </p>
        </div>
      </div>
      
      <div className="flex-1 overflow-hidden">
        {/* We need to use the client component we built previously */}
        <SignalFeedClient />
      </div>
    </div>
  );
}

// Just wrapping the actual client component to keep page clean
import SignalFeed from '@/components/radar/SignalFeed';
function SignalFeedClient() {
  return <SignalFeed />;
}
